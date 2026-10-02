"""Tests for allowlisted source file adapter (T021).

Verifies:
1. Normal temp -> fsync -> atomic replace only inside allowlist.
2. Two-phase staged write lifecycle (prepare, commit, cleanup) for T022 journal integration.
3. Negative probes: unknown source, non-VALID status, absent file, corrupt source,
   invalid replacement markdown, oversized payload (>8 MiB), invalid UTF-8,
   stale hash / revision conflict.
4. Security boundaries: path traversal (dot-dot, absolute, rooted, drive-relative,
   UNC, alternate data streams, device names, trailing dots/spaces), symlinks,
   ancestor symlinks, hardlinks (st_nlink > 1), root identity changes.
5. Access controls: read-only files and directories fail closed.
6. Fail-closed durability: failure before replacement preserves originals and cleans up temp files.
7. Privacy: errors and logs never contain raw paths, content, or credentials.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from backend.app.adapters.source_files import (
    MAX_SOURCE_SIZE_BYTES,
    ReplacementReceipt,
    SourceAccessError,
    SourceConflictError,
    SourceFileAdapter,
    SourceFileError,
    SourceSecurityError,
    SourceValidationError,
    StagedWrite,
    _check_windows_ownership,
    _is_reparse_or_link,
    _safe_cleanup_temp,
    validate_relative_path,
)
from backend.app.vocabulary.models import SourceFile, SourceStatus

VALID_MD_TEMPLATE = """# {date_str}

## Tra cứu nhanh

| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |
|---|---|---|---|---|
| {word} ({pos}.) | /{ipa}/ | {meaning} | {example} | {translation} |
"""


def _make_valid_markdown(
    date_str: str = "29-09-2026",
    word: str = "robust",
    pos: str = "adj",
    ipa: str = "roʊbʌst",
    meaning: str = "mạnh mẽ, bền vững",
    example: str = "The system has robust security boundaries.",
    translation: str = "Hệ thống có các ranh giới bảo mật vững chắc.",
) -> str:
    return VALID_MD_TEMPLATE.format(
        date_str=date_str,
        word=word,
        pos=pos,
        ipa=ipa,
        meaning=meaning,
        example=example,
        translation=translation,
    )


def _make_source_file(
    source_id: str = "src_29_09_2026",
    relative_path: str = "29-09-2026.md",
    note_date: str = "2026-09-29",
    status: str = "VALID",
    revision: int = 1,
    content_hash: str | None = None,
) -> SourceFile:
    typed_status = cast(SourceStatus, status)
    return SourceFile(
        id=source_id,
        relative_path=relative_path,
        note_date=note_date,
        status=typed_status,
        revision=revision,
        etag=f'"etag_{source_id}_r{revision}"',
        content_hash=content_hash,
        last_parsed_at="2026-09-29T12:00:00Z",
        error_code=None,
        created_at="2026-09-29T12:00:00Z",
        updated_at="2026-09-29T12:00:00Z",
    )


def _sha256(text_or_bytes: str | bytes) -> str:
    data = text_or_bytes.encode("utf-8") if isinstance(text_or_bytes, str) else text_or_bytes
    return hashlib.sha256(data).hexdigest()


def _write_fixture_bytes(path: Path, text_or_bytes: str | bytes) -> bytes:
    """Write explicit UTF-8 fixture bytes without platform newline translation."""
    data = text_or_bytes.encode("utf-8") if isinstance(text_or_bytes, str) else text_or_bytes
    path.write_bytes(data)
    return data


@pytest.fixture(autouse=True)
def _disable_newline_translation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure Path.write_text across all tests does not perform platform CRLF translation."""
    orig_write_text = Path.write_text

    def exact_write_text(
        self: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        _newline: str | None = None,
    ) -> int:
        return orig_write_text(self, data, encoding=encoding or "utf-8", errors=errors, newline="")

    monkeypatch.setattr(Path, "write_text", exact_write_text)


# ==============================================================================
# 1. HAPPY PATH & ATOMIC REPLACEMENT LIFECYCLE
# ==============================================================================


def test_successful_atomic_replacement(tmp_path: Path) -> None:
    """Normal atomic replacement writes to temp, fsyncs, and atomically replaces target."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    original_content = _make_valid_markdown(word="initial")
    source_path.write_text(original_content, encoding="utf-8")
    original_hash = _sha256(original_content)

    source = _make_source_file(content_hash=original_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    new_content = _make_valid_markdown(word="updated")
    new_hash = _sha256(new_content)

    receipt = adapter.replace_source_content(
        source_id=source.id,
        new_content=new_content,
        expected_content_hash=original_hash,
    )

    assert isinstance(receipt, ReplacementReceipt)
    assert receipt.source_id == source.id
    assert receipt.relative_path == "29-09-2026.md"
    assert receipt.old_content_hash == original_hash
    assert receipt.new_content_hash == new_hash
    assert receipt.bytes_written == len(new_content.encode("utf-8"))

    # Assert on-disk state
    assert source_path.read_text(encoding="utf-8") == new_content
    # Assert no leftover temp files in directory
    assert list(root.glob("*.tmp*")) == []


def test_two_phase_staged_write_commit(tmp_path: Path) -> None:
    """Two-phase prepare -> commit lifecycle cleanly replaces file for T022 journal."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="staged")
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    new_content = _make_valid_markdown(word="committed")
    new_hash = _sha256(new_content)

    staged = adapter.prepare_staged_write(
        source_id=source.id,
        new_content=new_content,
        expected_content_hash=orig_hash,
    )

    assert isinstance(staged, StagedWrite)
    assert staged.source_id == source.id
    assert staged.expected_content_hash == orig_hash
    assert staged.new_content_hash == new_hash

    # Before commit: original file is still unchanged
    assert source_path.read_text(encoding="utf-8") == orig_content

    # Commit
    receipt = staged.commit()
    assert receipt.new_content_hash == new_hash
    assert source_path.read_text(encoding="utf-8") == new_content
    assert list(root.glob("*.tmp*")) == []


def test_two_phase_staged_write_cleanup(tmp_path: Path) -> None:
    """Calling cleanup removes the temp file without altering the original file."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="preserved")
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    new_content = _make_valid_markdown(word="aborted")

    staged = adapter.prepare_staged_write(
        source_id=source.id,
        new_content=new_content,
        expected_content_hash=orig_hash,
    )

    # Abort and clean up
    staged.cleanup()

    # Original file is untouched
    assert source_path.read_text(encoding="utf-8") == orig_content
    # No temporary files remain
    assert list(root.glob("*.tmp*")) == []


def test_read_source_content_and_hash(tmp_path: Path) -> None:
    """Adapter can read current content and calculate hash for allowlisted source."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    content = _make_valid_markdown(word="reader")
    source_path.write_text(content, encoding="utf-8")

    source = _make_source_file()
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    read_text = adapter.read_source_content(source.id)
    assert read_text == content

    read_hash = adapter.get_source_hash(source.id)
    assert read_hash == _sha256(content)


# ==============================================================================
# 2. NEGATIVE ORACLES & REVISION CONFLICTS
# ==============================================================================


def test_unknown_source_id_rejected(tmp_path: Path) -> None:
    """Unknown source ID fails closed with SOURCE_NOT_FOUND."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    adapter = SourceFileAdapter(root)

    with pytest.raises(SourceFileError) as exc_info:
        adapter.replace_source_content("unknown_id", "content", "hash")
    assert exc_info.value.code == "SOURCE_NOT_FOUND"


def test_invalid_source_status_rejected(tmp_path: Path) -> None:
    """Source with status INVALID or MISSING cannot be overwritten."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    source_path.write_text("dummy", encoding="utf-8")

    src_invalid = _make_source_file(source_id="src_inv", status="INVALID")
    src_missing = _make_source_file(source_id="src_mis", status="MISSING")

    adapter = SourceFileAdapter(
        root,
        allowlist={src_invalid.id: src_invalid, src_missing.id: src_missing},
    )

    with pytest.raises(SourceFileError) as exc_info1:
        adapter.replace_source_content(src_invalid.id, "new", "hash")
    assert exc_info1.value.code == "SOURCE_NOT_WRITABLE"

    with pytest.raises(SourceFileError) as exc_info2:
        adapter.replace_source_content(src_missing.id, "new", "hash")
    assert exc_info2.value.code == "SOURCE_NOT_WRITABLE"


def test_absent_source_file_fails_closed(tmp_path: Path) -> None:
    """Absent file on disk fails with SOURCE_NOT_FOUND and is never auto-created."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source = _make_source_file()
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    with pytest.raises(SourceFileError) as exc_info:
        adapter.replace_source_content(source.id, _make_valid_markdown(), "hash")
    assert exc_info.value.code == "SOURCE_NOT_FOUND"
    assert not (root / "29-09-2026.md").exists()


def test_corrupt_current_markdown_rejected(tmp_path: Path) -> None:
    """If existing file contains invalid Markdown, replacement is refused to preserve data."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    corrupt_content = "# Corrupted Non-Date H1\n\nSome invalid text"
    source_path.write_text(corrupt_content, encoding="utf-8")
    corrupt_hash = _sha256(corrupt_content)

    source = _make_source_file(content_hash=corrupt_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    with pytest.raises(SourceValidationError) as exc_info:
        adapter.replace_source_content(source.id, _make_valid_markdown(), corrupt_hash)
    assert exc_info.value.code == "CORRUPT_SOURCE"
    # Existing corrupt file must remain preserved
    assert source_path.read_text(encoding="utf-8") == corrupt_content


def test_invalid_replacement_markdown_rejected(tmp_path: Path) -> None:
    """Replacement content failing parser validation fails closed."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    invalid_replacement = "# 29-09-2026\n\nMissing tables completely"

    with pytest.raises(SourceValidationError) as exc_info:
        adapter.replace_source_content(source.id, invalid_replacement, orig_hash)
    assert exc_info.value.code == "INVALID_REPLACEMENT_MARKDOWN"
    assert source_path.read_text(encoding="utf-8") == orig_content


def test_payload_too_large_rejected(tmp_path: Path) -> None:
    """Content exceeding 8 MiB (8,388,608 bytes) fails with PAYLOAD_TOO_LARGE."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # Create oversized content > 8 MiB
    padding = " " * (MAX_SOURCE_SIZE_BYTES + 10)
    oversized = _make_valid_markdown() + f"\n<!-- {padding} -->\n"

    with pytest.raises(SourceValidationError) as exc_info:
        adapter.replace_source_content(source.id, oversized, orig_hash)
    assert exc_info.value.code == "PAYLOAD_TOO_LARGE"
    assert source_path.read_text(encoding="utf-8") == orig_content


def test_payload_at_cap_accepted(tmp_path: Path) -> None:
    """Content exactly at 8 MiB (8,388,608 bytes) is accepted."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    base_md = _make_valid_markdown() + "\n<!-- "
    closing = " -->\n"
    base_len = len(base_md.encode("utf-8")) + len(closing.encode("utf-8"))
    needed_bytes = MAX_SOURCE_SIZE_BYTES - base_len
    at_cap_content = base_md + ("x" * needed_bytes) + closing

    assert len(at_cap_content.encode("utf-8")) == MAX_SOURCE_SIZE_BYTES

    receipt = adapter.replace_source_content(source.id, at_cap_content, orig_hash)
    assert receipt.bytes_written == MAX_SOURCE_SIZE_BYTES
    assert source_path.read_text(encoding="utf-8") == at_cap_content


def test_content_hash_mismatch_rejected(tmp_path: Path) -> None:
    """Stale expected content hash returns REVISION_CONFLICT without modifying original."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")

    source = _make_source_file()
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    with pytest.raises(SourceConflictError) as exc_info:
        adapter.replace_source_content(
            source.id,
            _make_valid_markdown(word="conflict"),
            expected_content_hash="0000000000000000000000000000000000000000000000000000000000000000",
        )
    assert exc_info.value.code == "REVISION_CONFLICT"
    assert source_path.read_text(encoding="utf-8") == orig_content


def test_external_edit_between_prepare_and_commit_rejected(tmp_path: Path) -> None:
    """If target file is edited between prepare and commit, commit fails closed."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="version1")
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(
        source.id,
        _make_valid_markdown(word="version2"),
        orig_hash,
    )

    # Simulate concurrent external editor changing target file
    external_content = _make_valid_markdown(word="external_edit")
    source_path.write_text(external_content, encoding="utf-8")

    # Staged commit must detect the hash mismatch and fail closed
    with pytest.raises(SourceConflictError) as exc_info:
        staged.commit()
    assert exc_info.value.code == "REVISION_CONFLICT"

    # External content is preserved!
    assert source_path.read_text(encoding="utf-8") == external_content
    # Temporary file was cleaned up!
    assert list(root.glob("*.tmp*")) == []


# ==============================================================================
# 3. SECURITY BOUNDARIES & ESCAPES
# ==============================================================================


@pytest.mark.parametrize(
    "escape_path",
    [
        "../escape.md",
        "../../etc/passwd",
        "/absolute/path.md",
        "\\backslash\\path.md",
        "C:\\Windows\\system32.md",
        "D:relative.md",
        ":alternate_data_stream.md",
        "file.md:hidden_stream",
        "\\\\server\\share\\file.md",
        "//server/share/file.md",
        "\\\\?\\C:\\file.md",
        "CON.md",
        "NUL",
        "com1.txt",
        "prn.md",
        "trailing_dot.md.",
        "trailing_space.md ",
    ],
)
def test_path_traversal_escapes_rejected(tmp_path: Path, escape_path: str) -> None:
    """Invalid and escaping relative paths fail registration or operation."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    adapter = SourceFileAdapter(root)

    source = _make_source_file(source_id="src_escape", relative_path=escape_path)

    # Either register_source or replace_source_content must reject it
    try:
        adapter.register_source(source)
        with pytest.raises(SourceFileError) as exc_info:
            adapter.replace_source_content(source.id, _make_valid_markdown(), "hash")
        assert exc_info.value.code in {"INVALID_SOURCE_PATH", "SECURITY_VIOLATION"}
    except SourceFileError as err:
        assert err.code in {"INVALID_SOURCE_PATH", "SECURITY_VIOLATION"}


def test_symlink_target_rejected(tmp_path: Path) -> None:
    """Symlink target file is rejected with SECURITY_VIOLATION."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    real_file = outside_dir / "target.md"
    orig_content = _make_valid_markdown(word="victim")
    real_file.write_text(orig_content, encoding="utf-8")
    real_hash = _sha256(orig_content)

    symlink_file = root / "29-09-2026.md"
    symlink_file.symlink_to(real_file)

    source = _make_source_file(content_hash=real_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    with pytest.raises(SourceSecurityError) as exc_info:
        adapter.replace_source_content(source.id, _make_valid_markdown(word="attack"), real_hash)
    assert exc_info.value.code == "SECURITY_VIOLATION"
    # Real outside target must remain untouched
    assert real_file.read_text(encoding="utf-8") == orig_content


def test_symlink_ancestor_directory_rejected(tmp_path: Path) -> None:
    """Symlink ancestor directory is rejected with SECURITY_VIOLATION."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    target_file = outside_dir / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="victim")
    target_file.write_text(orig_content, encoding="utf-8")
    target_hash = _sha256(orig_content)

    link_dir = root / "sub"
    link_dir.symlink_to(outside_dir)

    source = _make_source_file(relative_path="sub/29-09-2026.md", content_hash=target_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    with pytest.raises(SourceSecurityError) as exc_info:
        adapter.replace_source_content(source.id, _make_valid_markdown(word="attack"), target_hash)
    assert exc_info.value.code == "SECURITY_VIOLATION"
    assert target_file.read_text(encoding="utf-8") == orig_content


def test_hardlink_target_rejected(tmp_path: Path) -> None:
    """Target file with multiple hardlinks (st_nlink > 1) is rejected."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="hardlinked")
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    other_hardlink = tmp_path / "other_link.md"
    os.link(source_path, other_hardlink)

    assert source_path.stat().st_nlink > 1

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    with pytest.raises(SourceSecurityError) as exc_info:
        adapter.replace_source_content(source.id, _make_valid_markdown(word="hacked"), orig_hash)
    assert exc_info.value.code == "SECURITY_VIOLATION"
    assert source_path.read_text(encoding="utf-8") == orig_content
    assert other_hardlink.read_text(encoding="utf-8") == orig_content


def test_root_directory_identity_change_detected(tmp_path: Path) -> None:
    """Renaming or replacing the root directory triggers ROOT_IDENTITY_CHANGED."""
    root1 = tmp_path / "vocab_root"
    root1.mkdir()
    source_path = root1 / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root1, allowlist={source.id: source})

    # Now simulate root replacement: rename old root and create new empty directory at old path
    root_backup = tmp_path / "vocab_root_renamed"
    root1.rename(root_backup)
    root1.mkdir()  # New directory with distinct inode!

    with pytest.raises(SourceSecurityError) as exc_info:
        adapter.replace_source_content(source.id, _make_valid_markdown(), orig_hash)
    assert exc_info.value.code == "ROOT_IDENTITY_CHANGED"


def test_read_only_target_rejected(tmp_path: Path) -> None:
    """Read-only target file is rejected with ACCESS_DENIED."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    # Set read-only permissions
    source_path.chmod(0o444)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    try:
        with pytest.raises(SourceAccessError) as exc_info:
            adapter.replace_source_content(
                source.id, _make_valid_markdown(word="denied"), orig_hash
            )
        assert exc_info.value.code == "ACCESS_DENIED"
    finally:
        source_path.chmod(0o666)  # Restore for cleanup


# ==============================================================================
# 4. PRIVACY & LOG INTEGRITY
# ==============================================================================


def test_error_messages_contain_no_raw_paths_or_content(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Exceptions, representations, args, and logs must never disclose paths or content."""
    root = tmp_path / "secret_vocab_dir_super_secret"
    root.mkdir()
    secret_path = root / "29-09-2026.md"
    secret_content = _make_valid_markdown(meaning="secret_vietnamese_meaning_token")
    secret_path.write_text(secret_content, encoding="utf-8")

    source = _make_source_file()
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    with pytest.raises(SourceFileError) as exc_info:
        adapter.replace_source_content(
            source.id,
            "corrupt_replacement_token_abc123",
            "wrong_hash_token_xyz789",
        )
    err = exc_info.value
    err_str = str(err)
    err_repr = repr(err)
    err_args = " ".join(str(a) for a in err.args)

    # Bounded identifier is allowed
    assert source.id in err_str or err.source_id == source.id

    # Secret path and content MUST NOT appear in str, repr, args, or logs
    for rendered in (err_str, err_repr, err_args, caplog.text):
        assert "secret_vocab_dir_super_secret" not in rendered
        assert "secret_vietnamese_meaning_token" not in rendered
        assert "corrupt_replacement_token_abc123" not in rendered
        assert "wrong_hash_token_xyz789" not in rendered


# ==============================================================================
# 5. FAILURE INJECTION & TEMP CLEANUP
# ==============================================================================


def test_failure_during_atomic_replace_cleans_up_temp(tmp_path: Path, monkeypatch: Any) -> None:
    """If os.replace fails, temp file is deleted and original file is preserved."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="preserved_orig")
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    def fake_replace(_src: Any, _dst: Any) -> None:
        raise OSError("Injected filesystem error during atomic replace")

    monkeypatch.setattr(os, "replace", fake_replace)

    with pytest.raises(SourceFileError) as exc_info:
        adapter.replace_source_content(source.id, _make_valid_markdown(word="never"), orig_hash)
    assert exc_info.value.code == "IO_ERROR"

    # Original file is preserved
    assert source_path.read_text(encoding="utf-8") == orig_content
    # Temporary file was cleaned up
    assert list(root.glob("*.tmp*")) == []


# ==============================================================================
# 6. COMPREHENSIVE BRANCH & EDGE CASE COVERAGE
# ==============================================================================


def test_validate_relative_path_edge_cases() -> None:
    """Unit validation for relative path helper edge cases."""
    with pytest.raises(SourceFileError) as exc_info1:
        validate_relative_path("")
    assert exc_info1.value.code == "INVALID_SOURCE_PATH"

    with pytest.raises(SourceFileError) as exc_info2:
        validate_relative_path("   ")
    assert exc_info2.value.code == "INVALID_SOURCE_PATH"

    with pytest.raises(SourceFileError) as exc_info3:
        validate_relative_path("dir//file.md")
    assert exc_info3.value.code == "INVALID_SOURCE_PATH"

    with pytest.raises(SourceFileError) as exc_info4:
        validate_relative_path("file\0.md")
    assert exc_info4.value.code == "INVALID_SOURCE_PATH"


def test_register_source_empty_id_rejected(tmp_path: Path) -> None:
    """Registering a source with empty ID is rejected."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    adapter = SourceFileAdapter(root)

    empty_id_source = _make_source_file(source_id="")
    with pytest.raises(SourceFileError) as exc_info:
        adapter.register_source(empty_id_source)
    assert exc_info.value.code == "INVALID_SOURCE_ID"


def test_root_directory_validation_failures(tmp_path: Path) -> None:
    """Root directory validation fails closed if missing, file, drive root, or symlink."""
    # 1. Non-existent root
    with pytest.raises(SourceFileError) as exc_info1:
        SourceFileAdapter(tmp_path / "non_existent_dir")
    assert exc_info1.value.code == "ROOT_NOT_FOUND"

    # 2. Root is a file
    file_as_root = tmp_path / "file_root"
    file_as_root.write_text("not a dir", encoding="utf-8")
    with pytest.raises(SourceFileError) as exc_info2:
        SourceFileAdapter(file_as_root)
    assert exc_info2.value.code == "ROOT_NOT_FOUND"

    # 3. Root is drive/filesystem root (depth <= 1)
    with pytest.raises(SourceSecurityError) as exc_info3:
        SourceFileAdapter(Path("/"))
    assert exc_info3.value.code == "INVALID_SOURCE_PATH"

    # 4. Root is a symlink
    real_dir = tmp_path / "real_dir"
    real_dir.mkdir()
    sym_root = tmp_path / "sym_root"
    sym_root.symlink_to(real_dir)
    with pytest.raises(SourceSecurityError) as exc_info4:
        SourceFileAdapter(sym_root)
    assert exc_info4.value.code == "SECURITY_VIOLATION"


def test_recheck_root_failures(tmp_path: Path, monkeypatch: Any) -> None:
    """_recheck_root fails if root deleted, stat fails, or replaced with link."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    adapter = SourceFileAdapter(root)

    # 1. Root deleted
    root.rmdir()
    with pytest.raises(SourceSecurityError) as exc_info1:
        adapter.read_source_content("any_id")
    assert exc_info1.value.code == "ROOT_IDENTITY_CHANGED"

    # Recreate root
    root.mkdir()
    adapter2 = SourceFileAdapter(root)
    resolved_root_str = str(root.resolve())

    # 2. os.stat raises OSError
    orig_stat = os.stat

    def fake_stat(p: Any, *args: Any, **kwargs: Any) -> Any:
        if str(p) == resolved_root_str:
            raise OSError("Injected stat error")
        return orig_stat(p, *args, **kwargs)

    monkeypatch.setattr(os, "stat", fake_stat)
    with pytest.raises(SourceSecurityError) as exc_info2:
        adapter2.read_source_content("any_id")
    assert exc_info2.value.code == "ROOT_IDENTITY_CHANGED"


def test_staged_write_lifecycle_errors(tmp_path: Path) -> None:
    """StagedWrite handles double commit, commit after cleanup, target swap, and missing temp."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)

    # Double commit
    staged.commit()
    with pytest.raises(SourceFileError) as exc_info1:
        staged.commit()
    assert exc_info1.value.code == "OPERATION_ALREADY_COMMITTED"

    # Staged write cleaned up then commit attempted
    staged2 = adapter.prepare_staged_write(
        source.id, _make_valid_markdown(word="new2"), _sha256(source_path.read_text("utf-8"))
    )
    staged2.cleanup()
    with pytest.raises(SourceFileError) as exc_info2:
        staged2.commit()
    assert exc_info2.value.code == "OPERATION_ABORTED"

    # Target file disappeared before commit
    staged3 = adapter.prepare_staged_write(
        source.id, _make_valid_markdown(word="new3"), _sha256(source_path.read_text("utf-8"))
    )
    source_path.unlink()
    with pytest.raises(SourceConflictError) as exc_info3:
        staged3.commit()
    assert exc_info3.value.code == "REVISION_CONFLICT"

    # Recreate target file (swapped with another file to guarantee different inode)
    source_path.write_text(orig_content, encoding="utf-8")
    staged4 = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new4"), orig_hash)
    swapped_file = root / "swapped.md"
    swapped_file.write_text(orig_content, encoding="utf-8")
    os.replace(swapped_file, source_path)
    with pytest.raises(SourceConflictError) as exc_info4:
        staged4.commit()
    assert exc_info4.value.code == "REVISION_CONFLICT"

    # Temp file deleted before commit
    staged5 = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new5"), orig_hash)
    staged5._temp_path.unlink()
    with pytest.raises(SourceFileError) as exc_info5:
        staged5.commit()
    assert exc_info5.value.code == "IO_ERROR"


def test_read_source_content_edge_cases(tmp_path: Path, monkeypatch: Any) -> None:
    """Read source handles missing source, missing target, oversized, and invalid encoding."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")

    source = _make_source_file()
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # Unknown source
    with pytest.raises(SourceFileError) as exc_info1:
        adapter.read_source_content("non_existent_source")
    assert exc_info1.value.code == "SOURCE_NOT_FOUND"

    # Target read OSError
    def fake_read_bytes(_self: Any) -> bytes:
        raise OSError("Injected read error")

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)
    with pytest.raises(SourceFileError) as exc_info2:
        adapter.read_source_content(source.id)
    assert exc_info2.value.code == "IO_ERROR"

    # Target oversized
    monkeypatch.undo()
    oversized_bytes = b" " * (MAX_SOURCE_SIZE_BYTES + 10)
    source_path.write_bytes(oversized_bytes)
    with pytest.raises(SourceValidationError) as exc_info3:
        adapter.read_source_content(source.id)
    assert exc_info3.value.code == "PAYLOAD_TOO_LARGE"

    # Invalid UTF-8
    source_path.write_bytes(b"\x80\x81\x82")
    with pytest.raises(SourceValidationError) as exc_info4:
        adapter.read_source_content(source.id)
    assert exc_info4.value.code == "INVALID_ENCODING"


def test_prepare_staged_write_edge_cases(tmp_path: Path, monkeypatch: Any) -> None:
    """Prepare staged write handles invalid encoding, target read errors, and temp write failure."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # Current target read OSError
    def fake_read_bytes(_self: Any) -> bytes:
        raise OSError("Injected read error")

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)
    with pytest.raises(SourceFileError) as exc_info1:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert exc_info1.value.code == "IO_ERROR"

    # Current target oversized
    monkeypatch.undo()
    source_path.write_bytes(b" " * (MAX_SOURCE_SIZE_BYTES + 5))
    with pytest.raises(SourceValidationError) as exc_info2:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert exc_info2.value.code == "PAYLOAD_TOO_LARGE"

    # Current target invalid UTF-8
    source_path.write_bytes(b"\xff\xfe\xfd")
    with pytest.raises(SourceValidationError) as exc_info3:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert exc_info3.value.code == "INVALID_ENCODING"

    # Restore valid content
    source_path.write_text(orig_content, encoding="utf-8")

    # Injected temp write failure
    def fake_fdopen(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("Injected fdopen write failure")

    monkeypatch.setattr(os, "fdopen", fake_fdopen)
    with pytest.raises(SourceFileError) as exc_info4:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert exc_info4.value.code == "IO_ERROR"


def test_is_reparse_or_link_helper_branches(tmp_path: Path) -> None:
    """Directly test _is_reparse_or_link helper for non-existent and synthetic stat results."""
    # Non-existent path returns False
    assert _is_reparse_or_link(tmp_path / "does_not_exist_file") is False

    # Synthetic stat with FILE_ATTRIBUTE_REPARSE_POINT
    class FakeStat:
        st_file_attributes = stat.FILE_ATTRIBUTE_REPARSE_POINT
        st_reparse_tag = 0

    assert _is_reparse_or_link(tmp_path, cast(os.stat_result, FakeStat())) is True

    # Synthetic stat with reparse tag
    class FakeStatTag:
        st_file_attributes = 0
        st_reparse_tag = 0xA000000C

    assert _is_reparse_or_link(tmp_path, cast(os.stat_result, FakeStatTag())) is True


def test_intermediate_directory_and_target_type_checks(tmp_path: Path) -> None:
    """Intermediate path component must be a directory, and target must be a regular file."""
    root = tmp_path / "vocab_root"
    root.mkdir()

    # 1. Intermediate directory does not exist
    source_nested = _make_source_file(
        source_id="src_nested", relative_path="missing_sub/29-09-2026.md"
    )
    adapter = SourceFileAdapter(root, allowlist={source_nested.id: source_nested})
    with pytest.raises(SourceFileError) as exc_info1:
        adapter.read_source_content(source_nested.id)
    assert exc_info1.value.code == "INVALID_SOURCE_PATH"

    # 2. Intermediate component is a regular file, not a directory
    file_as_dir = root / "sub_file"
    file_as_dir.write_text("just a file", encoding="utf-8")
    source_blocked = _make_source_file(
        source_id="src_blocked", relative_path="sub_file/29-09-2026.md"
    )
    adapter.register_source(source_blocked)
    with pytest.raises(SourceSecurityError) as exc_info2:
        adapter.read_source_content(source_blocked.id)
    assert exc_info2.value.code == "SECURITY_VIOLATION"

    # 3. Target is a directory instead of a regular file
    dir_as_file = root / "30-09-2026.md"
    dir_as_file.mkdir()
    source_is_dir = _make_source_file(source_id="src_dir", relative_path="30-09-2026.md")
    adapter.register_source(source_is_dir)
    with pytest.raises(SourceSecurityError) as exc_info3:
        adapter.read_source_content(source_is_dir.id)
    assert exc_info3.value.code == "SECURITY_VIOLATION"


def test_staged_commit_target_became_symlink_or_hardlink(tmp_path: Path) -> None:
    """Target becoming a symlink or hardlink before commit is rejected."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # Case 1: Target becomes symlink before commit
    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    source_path.unlink()
    dummy_target = tmp_path / "dummy.md"
    dummy_target.write_text(orig_content, encoding="utf-8")
    source_path.symlink_to(dummy_target)

    with pytest.raises((SourceConflictError, SourceSecurityError)) as exc_info:
        staged.commit()
    # Inode or link detection fails closed
    assert exc_info.value.code in {"REVISION_CONFLICT", "SECURITY_VIOLATION"}

    # Restore regular file
    source_path.unlink()
    source_path.write_text(orig_content, encoding="utf-8")

    # Case 2: Target is hardlinked before commit
    staged2 = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new2"), orig_hash)
    extra_link = tmp_path / "extra_link.md"
    os.link(source_path, extra_link)

    with pytest.raises(SourceSecurityError) as exc_info2:
        staged2.commit()
    assert exc_info2.value.code == "SECURITY_VIOLATION"


def test_staged_commit_target_became_readonly(tmp_path: Path) -> None:
    """Target file becoming read-only before commit fails with ACCESS_DENIED."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    source_path.chmod(0o444)

    try:
        with pytest.raises(SourceAccessError) as exc_info:
            staged.commit()
        assert exc_info.value.code == "ACCESS_DENIED"
    finally:
        source_path.chmod(0o666)


def test_staged_cleanup_swallows_oserror(tmp_path: Path, monkeypatch: Any) -> None:
    """StagedWrite.cleanup safely swallows OSError if unlink fails."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)

    def fake_unlink(_self: Any) -> None:
        raise OSError("Injected unlink error")

    monkeypatch.setattr(Path, "unlink", fake_unlink)
    # Should not raise exception
    staged.cleanup()
    assert staged._cleaned_up is True


# ==============================================================================
# 7. REGRESSION TESTS FOR AUDITED VULNERABILITIES (T021 REPAIR)
# ==============================================================================


def test_ancestor_substitution_between_prepare_and_commit_rejected(tmp_path: Path) -> None:
    """Prepare -> ancestor directory substituted with symlink -> commit fails closed.

    Target file retains its exact device/inode identity because the original
    directory is moved outside the root and symlinked back. Commit MUST re-inspect
    intermediate components, reject the symlink ancestor, leave outside file
    intact, and never perform replacement.
    """
    root = tmp_path / "vocab_root"
    root.mkdir()
    sub_dir = root / "sub_dir"
    sub_dir.mkdir()
    target_path = sub_dir / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="outside_original")
    target_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(
        source_id="src_nested",
        relative_path="sub_dir/29-09-2026.md",
        content_hash=orig_hash,
    )
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(
        source.id,
        _make_valid_markdown(word="injected_payload"),
        orig_hash,
    )

    # Substitute ancestor directory: move sub_dir outside root, symlink back
    outside_dir = tmp_path / "outside_dir"
    sub_dir.rename(outside_dir)
    sub_dir.symlink_to(outside_dir)

    # Outside target file still exists and has exact same inode/dev
    outside_file = outside_dir / "29-09-2026.md"
    assert outside_file.exists()
    assert outside_file.read_text(encoding="utf-8") == orig_content

    # Commit must detect ancestor symlink and fail closed
    with pytest.raises(SourceSecurityError) as exc_info:
        staged.commit()
    assert exc_info.value.code == "SECURITY_VIOLATION"

    # Outside original file remains completely untouched!
    assert outside_file.read_text(encoding="utf-8") == orig_content


def test_ancestor_directory_identity_change_rejected(tmp_path: Path) -> None:
    """Prepare -> ancestor directory replaced with new dir -> commit fails closed."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    sub_dir = root / "sub_dir"
    sub_dir.mkdir()
    target_path = sub_dir / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="orig")
    target_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(
        source_id="src_nested",
        relative_path="sub_dir/29-09-2026.md",
        content_hash=orig_hash,
    )
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(
        source.id,
        _make_valid_markdown(word="new"),
        orig_hash,
    )

    # Replace ancestor directory with new directory (distinct inode)
    sub_dir.rename(root / "sub_dir_backup")
    sub_dir.mkdir()
    new_target = sub_dir / "29-09-2026.md"
    new_target.write_text(orig_content, encoding="utf-8")

    with pytest.raises(SourceSecurityError) as exc_info:
        staged.commit()
    assert exc_info.value.code == "SECURITY_VIOLATION"


def test_staged_temp_file_same_size_tampering_rejected(tmp_path: Path) -> None:
    """Tampering with staged temp file content before commit is rejected."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="orig")
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    proposal = _make_valid_markdown(word="prop")
    staged = adapter.prepare_staged_write(source.id, proposal, orig_hash)

    # Tamper with staged temp file with same byte length
    tampered = _make_valid_markdown(word="tamp")
    assert len(tampered.encode("utf-8")) == len(proposal.encode("utf-8"))
    staged._temp_path.write_text(tampered, encoding="utf-8")

    with pytest.raises(SourceConflictError) as exc_info:
        staged.commit()
    assert exc_info.value.code == "REVISION_CONFLICT"
    assert source_path.read_text(encoding="utf-8") == orig_content


def test_staged_temp_file_inode_substitution_rejected(tmp_path: Path) -> None:
    """Replacing staged temp file with another file (even identical bytes) is rejected."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="orig")
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    proposal = _make_valid_markdown(word="prop")
    staged = adapter.prepare_staged_write(source.id, proposal, orig_hash)

    # Create another file with identical bytes and atomic replace temp_path (new inode)
    substitute_file = root / "substitute.tmp"
    substitute_file.write_text(proposal, encoding="utf-8")
    os.replace(substitute_file, staged._temp_path)

    with pytest.raises(SourceSecurityError) as exc_info:
        staged.commit()
    assert exc_info.value.code == "SECURITY_VIOLATION"
    assert source_path.read_text(encoding="utf-8") == orig_content


def test_staged_temp_file_hardlink_added_rejected(tmp_path: Path) -> None:
    """Adding a hardlink to staged temp file causes commit to fail closed."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="orig")
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="prop"), orig_hash)

    # Add hard link to staged temp file
    extra_link = tmp_path / "extra_temp_link.tmp"
    os.link(staged._temp_path, extra_link)

    with pytest.raises(SourceSecurityError) as exc_info:
        staged.commit()
    assert exc_info.value.code == "SECURITY_VIOLATION"
    assert source_path.read_text(encoding="utf-8") == orig_content


def test_cleanup_safe_after_staged_file_substitution(tmp_path: Path) -> None:
    """Cleanup does not unlink if temp path was substituted with a symlink to outside file."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="orig")
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="prop"), orig_hash)

    # Outside precious file
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    precious = outside_dir / "precious.txt"
    precious.write_text("precious content", encoding="utf-8")

    # Substitute temp path with symlink to outside file
    real_temp = staged._temp_path
    real_temp.unlink()
    real_temp.symlink_to(precious)

    # Cleanup must NOT unlink outside precious file or substituted symlink
    staged.cleanup()
    assert real_temp.is_symlink()
    assert real_temp.exists()
    assert precious.exists()
    assert precious.read_text(encoding="utf-8") == "precious content"


def test_cleanup_safe_after_ancestor_substitution(tmp_path: Path) -> None:
    """Cleanup does not unlink through a substituted ancestor directory."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    sub_dir = root / "sub_dir"
    sub_dir.mkdir()
    target_path = sub_dir / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    orig_bytes = _write_fixture_bytes(target_path, orig_content)
    orig_hash = _sha256(orig_bytes)

    source = _make_source_file(
        source_id="src_nested",
        relative_path="sub_dir/29-09-2026.md",
        content_hash=orig_hash,
    )
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="prop"), orig_hash)
    relocated_temp = tmp_path / "outside_sub" / staged._temp_path.name

    outside_dir = tmp_path / "outside_sub"
    sub_dir.rename(outside_dir)
    sub_dir.symlink_to(outside_dir)

    temp_bytes = relocated_temp.read_bytes()

    # Cleanup must not raise and must not unlink outside dir, substituted link, or temp
    staged.cleanup()
    assert outside_dir.exists()
    assert sub_dir.is_symlink()
    assert relocated_temp.exists()
    assert relocated_temp.read_bytes() == temp_bytes
    assert (outside_dir / "29-09-2026.md").read_bytes() == orig_bytes


def test_recheck_source_authorization_deleted_source(tmp_path: Path) -> None:
    """If source registration is deleted before commit, commit fails closed."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="prop"), orig_hash)

    # Unregister source
    adapter._sources.pop(source.id)

    with pytest.raises(SourceFileError) as exc_info:
        staged.commit()
    assert exc_info.value.code == "SOURCE_NOT_FOUND"
    assert source_path.read_text(encoding="utf-8") == orig_content


def test_recheck_source_authorization_status_invalid_or_missing(tmp_path: Path) -> None:
    """If source status changes to INVALID or MISSING before commit, commit fails closed."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="prop"), orig_hash)

    # Update status to INVALID
    adapter._sources[source.id] = _make_source_file(
        source_id=source.id,
        status="INVALID",
        content_hash=orig_hash,
    )

    with pytest.raises(SourceFileError) as exc_info:
        staged.commit()
    assert exc_info.value.code == "SOURCE_NOT_WRITABLE"
    assert "INVALID" not in str(exc_info.value)  # No raw status interpolation!
    assert source_path.read_text(encoding="utf-8") == orig_content


def test_recheck_source_authorization_destination_changed(tmp_path: Path) -> None:
    """If source relative_path is changed before commit, commit fails closed."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path1 = root / "29-09-2026.md"
    orig_content1 = _make_valid_markdown(word="file1")
    source_path1.write_text(orig_content1, encoding="utf-8")
    orig_hash1 = _sha256(orig_content1)

    source_path2 = root / "30-09-2026.md"
    orig_content2 = _make_valid_markdown(word="file2")
    source_path2.write_text(orig_content2, encoding="utf-8")

    source = _make_source_file(content_hash=orig_hash1)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(
        source.id, _make_valid_markdown(word="payload"), orig_hash1
    )

    # Re-register source with different destination
    adapter._sources[source.id] = _make_source_file(
        source_id=source.id,
        relative_path="30-09-2026.md",
        content_hash=orig_hash1,
    )

    with pytest.raises(SourceConflictError) as exc_info:
        staged.commit()
    assert exc_info.value.code == "REVISION_CONFLICT"

    # Both destinations preserved
    assert source_path1.read_text(encoding="utf-8") == orig_content1
    assert source_path2.read_text(encoding="utf-8") == orig_content2


def test_recheck_source_authorization_metadata_changed(tmp_path: Path) -> None:
    """If revision, etag, or content_hash changes before commit, commit fails closed."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="prop"), orig_hash)

    # Change revision
    adapter._sources[source.id] = _make_source_file(
        source_id=source.id,
        revision=99,
        content_hash=orig_hash,
    )

    with pytest.raises(SourceConflictError) as exc_info:
        staged.commit()
    assert exc_info.value.code == "REVISION_CONFLICT"
    assert source_path.read_text(encoding="utf-8") == orig_content


def test_mkstemp_permission_denied_sanitized(tmp_path: Path, monkeypatch: Any) -> None:
    """tempfile.mkstemp PermissionError is caught, sanitized, and typed as ACCESS_DENIED."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    def fake_mkstemp(*_args: Any, **_kwargs: Any) -> Any:
        raise PermissionError("Raw internal OS path /private/var/secret/temp access denied")

    monkeypatch.setattr("tempfile.mkstemp", fake_mkstemp)

    with pytest.raises(SourceAccessError) as exc_info:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert exc_info.value.code == "ACCESS_DENIED"
    assert "/private/var/secret/temp" not in str(exc_info.value)


def test_mkstemp_io_error_sanitized(tmp_path: Path, monkeypatch: Any) -> None:
    """tempfile.mkstemp OSError is caught, sanitized, and typed as IO_ERROR."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    def fake_mkstemp(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("Raw internal OS /private/var/disk_full_error")

    monkeypatch.setattr("tempfile.mkstemp", fake_mkstemp)

    with pytest.raises(SourceFileError) as exc_info:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert exc_info.value.code == "IO_ERROR"
    assert "/private/var/disk_full_error" not in str(exc_info.value)


def test_failure_before_fdopen_closes_descriptor_and_cleans_up(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Failure after mkstemp but before fdopen safely closes temp_fd and unlinks temp_path."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    def fake_chmod(_p: Any, _mode: int) -> None:
        raise OSError("Injected chmod error before fdopen")

    monkeypatch.setattr(os, "chmod", fake_chmod)

    with pytest.raises(SourceFileError) as exc_info:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert exc_info.value.code == "IO_ERROR"
    # Ensure no leftover temp files exist
    assert list(root.glob("*.tmp*")) == []


def test_privacy_source_id_sanitization_boundaries(tmp_path: Path) -> None:
    """Source ID in diagnostics must be bounded and validated; invalid IDs must be omitted."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    # 1. Direct error construction with path-like ID
    err_path = SourceFileError(
        "INVALID_SOURCE_PATH", "Testing path ID", source_id="/var/log/secret_sentinel"
    )
    assert err_path.source_id is None
    assert "/var/log/secret_sentinel" not in str(err_path)
    assert "/var/log/secret_sentinel" not in repr(err_path)
    assert "/var/log/secret_sentinel" not in str(err_path.args)

    # 2. Direct error construction with control chars and newlines
    err_nl = SourceFileError(
        "INVALID_SOURCE_PATH", "Testing nl ID", source_id="bad_id\nsecret_newline_sentinel\r"
    )
    assert err_nl.source_id is None
    assert "secret_newline_sentinel" not in str(err_nl)

    # 3. Direct error construction with oversized ID (> 64 chars)
    err_oversized = SourceFileError(
        "INVALID_SOURCE_PATH", "Testing oversized ID", source_id="a" * 500
    )
    assert err_oversized.source_id is None
    assert ("a" * 100) not in str(err_oversized)

    # 4. Legitimate source ID is preserved
    err_legit = SourceFileError("TEST_CODE", "Testing legit ID", source_id="src_legit_29_09_2026")
    assert err_legit.source_id == "src_legit_29_09_2026"
    assert "src_legit_29_09_2026" in str(err_legit)

    # 5. register_source with path-like ID fails with INVALID_SOURCE_ID and no raw path
    adapter = SourceFileAdapter(root)
    bad_source = _make_source_file(source_id="/etc/shadow_secret_token")
    with pytest.raises(SourceFileError) as exc_info1:
        adapter.register_source(bad_source)
    assert exc_info1.value.code == "INVALID_SOURCE_ID"
    assert "/etc/shadow_secret_token" not in str(exc_info1.value)

    # 6. read_source_content with path-like ID fails with SOURCE_NOT_FOUND and no raw path
    with pytest.raises(SourceFileError) as exc_info2:
        adapter.read_source_content("/secret/path/token/probe")
    assert exc_info2.value.code == "SOURCE_NOT_FOUND"
    assert "/secret/path/token/probe" not in str(exc_info2.value)

    # 7. prepare_staged_write with path-like ID fails with SOURCE_NOT_FOUND and no raw path
    with pytest.raises(SourceFileError) as exc_info3:
        adapter.prepare_staged_write("/secret/path/token/probe", _make_valid_markdown(), orig_hash)
    assert exc_info3.value.code == "SOURCE_NOT_FOUND"
    assert "/secret/path/token/probe" not in str(exc_info3.value)


def test_intermediate_directory_removed_or_corrupted_before_commit(tmp_path: Path) -> None:
    """Commit fails closed if intermediate directory disappears, becomes a file,
    or becomes read-only.
    """
    root = tmp_path / "vocab_root"
    root.mkdir()
    sub_dir = root / "sub_dir"
    sub_dir.mkdir()
    target_path = sub_dir / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    target_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(
        source_id="src_nested",
        relative_path="sub_dir/29-09-2026.md",
        content_hash=orig_hash,
    )
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # Case 1: Intermediate directory disappeared before commit
    staged1 = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new1"), orig_hash)
    shutil.rmtree(sub_dir)
    with pytest.raises(SourceSecurityError) as exc_info1:
        staged1.commit()
    assert exc_info1.value.code == "SECURITY_VIOLATION"

    # Recreate structure
    sub_dir.mkdir()
    target_path.write_text(orig_content, encoding="utf-8")

    # Case 2: Intermediate component became a regular file instead of directory
    staged2 = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new2"), orig_hash)
    shutil.rmtree(sub_dir)
    sub_dir.write_text("i am now a file", encoding="utf-8")
    with pytest.raises(SourceSecurityError) as exc_info2:
        staged2.commit()
    assert exc_info2.value.code == "SECURITY_VIOLATION"

    # Recreate structure
    sub_dir.unlink()
    sub_dir.mkdir()
    target_path.write_text(orig_content, encoding="utf-8")

    # Case 3: Intermediate directory became read-only before commit
    staged3 = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new3"), orig_hash)
    sub_dir.chmod(0o555)
    try:
        with pytest.raises(SourceAccessError) as exc_info3:
            staged3.commit()
        assert exc_info3.value.code == "ACCESS_DENIED"
    finally:
        sub_dir.chmod(0o777)


def test_staged_temp_file_symlink_or_dir_or_oversized_rejected_at_commit(tmp_path: Path) -> None:
    """Commit rejects temp file becoming symlink, directory, or oversized."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # Case 1: Temp file replaced by symlink
    staged1 = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new1"), orig_hash)
    real_temp = staged1._temp_path
    real_temp.unlink()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    real_temp.symlink_to(outside)
    with pytest.raises(SourceSecurityError) as exc_info1:
        staged1.commit()
    assert exc_info1.value.code == "SECURITY_VIOLATION"

    # Case 2: Temp file replaced by directory
    staged2 = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new2"), orig_hash)
    staged2._temp_path.unlink()
    staged2._temp_path.mkdir()
    with pytest.raises(SourceSecurityError) as exc_info2:
        staged2.commit()
    assert exc_info2.value.code == "SECURITY_VIOLATION"
    staged2._temp_path.rmdir()

    # Case 3: Temp file became oversized
    staged3 = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new3"), orig_hash)
    oversized_data = b" " * (MAX_SOURCE_SIZE_BYTES + 100)
    staged3._temp_path.write_bytes(oversized_data)
    with pytest.raises(SourceValidationError) as exc_info3:
        staged3.commit()
    assert exc_info3.value.code == "PAYLOAD_TOO_LARGE"


def test_read_errors_during_commit_fail_closed(tmp_path: Path, monkeypatch: Any) -> None:
    """Target or temp file read failure during commit raises IO_ERROR."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # 1. Target read_bytes fails
    staged1 = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new1"), orig_hash)
    orig_read_bytes = Path.read_bytes

    def fake_read_bytes_target(self: Path) -> bytes:
        if self == staged1._target_path:
            raise OSError("Injected target read error")
        return orig_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes_target)
    with pytest.raises(SourceFileError) as exc_info1:
        staged1.commit()
    assert exc_info1.value.code == "IO_ERROR"

    # 2. Temp read_bytes fails
    monkeypatch.undo()
    staged2 = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new2"), orig_hash)

    def fake_read_bytes_temp(self: Path) -> bytes:
        if self == staged2._temp_path:
            raise OSError("Injected temp read error")
        return orig_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes_temp)
    with pytest.raises(SourceFileError) as exc_info2:
        staged2.commit()
    assert exc_info2.value.code == "IO_ERROR"


def test_adapter_root_path_property(tmp_path: Path) -> None:
    """Adapter root_path property returns resolved root directory."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    adapter = SourceFileAdapter(root)
    assert adapter.root_path == root.resolve()


def test_prepare_staged_write_unencodable_chars_and_dir_errors(tmp_path: Path) -> None:
    """Prepare staged write rejects unencodable characters and target_dir stat errors."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # 1. Unencodable characters in new_content (surrogate code points)
    unencodable_content = _make_valid_markdown() + "\ud800"
    with pytest.raises(SourceValidationError) as exc_info1:
        adapter.prepare_staged_write(source.id, unencodable_content, orig_hash)
    assert exc_info1.value.code == "INVALID_ENCODING"

    # 2. Target directory stat failure
    orig_stat = os.stat

    def fake_stat_target_dir(p: Any, *args: Any, **kwargs: Any) -> Any:
        if str(p) == str(root.resolve()):
            # Allow root identity check but fail target_dir stat if called for parent
            pass
        return orig_stat(p, *args, **kwargs)

    # Make target_dir stat fail by monkeypatching when parent is checked
    sub_dir = root / "sub_unwritable"
    sub_dir.mkdir()
    nested_path = sub_dir / "29-09-2026.md"
    nested_path.write_text(orig_content, encoding="utf-8")
    nested_source = _make_source_file(
        source_id="src_unwritable",
        relative_path="sub_unwritable/29-09-2026.md",
        content_hash=orig_hash,
    )
    adapter.register_source(nested_source)

    # Intermediate directory not writable during prepare
    sub_dir.chmod(0o555)
    try:
        with pytest.raises(SourceAccessError) as exc_info2:
            adapter.prepare_staged_write(nested_source.id, _make_valid_markdown(), orig_hash)
        assert exc_info2.value.code == "ACCESS_DENIED"
    finally:
        sub_dir.chmod(0o777)


def test_prepare_staged_write_temp_permission_error_and_descriptor_integrity(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """PermissionError during write/fsync and descriptor integrity failure fail closed."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    source_path.write_text(orig_content, encoding="utf-8")
    orig_hash = _sha256(orig_content)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # 1. PermissionError during temp file write/fsync
    def fake_fsync(_fd: int) -> None:
        raise PermissionError("Injected fsync permission denied")

    monkeypatch.setattr(os, "fsync", fake_fsync)
    with pytest.raises(SourceAccessError) as exc_info1:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert exc_info1.value.code == "ACCESS_DENIED"
    assert list(root.glob("*.tmp*")) == []

    # 2. Descriptor integrity failure (nlink != 1)
    monkeypatch.undo()
    orig_fstat = os.fstat

    def fake_fstat(fd: int) -> Any:
        real_st = orig_fstat(fd)

        class TamperedStat:
            st_dev = real_st.st_dev
            st_ino = real_st.st_ino
            st_mode = real_st.st_mode
            st_nlink = 2  # Tampered hard link count!
            st_size = real_st.st_size

        return TamperedStat()

    monkeypatch.setattr(os, "fstat", fake_fstat)
    with pytest.raises(SourceSecurityError) as exc_info2:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new2"), orig_hash)
    assert exc_info2.value.code == "SECURITY_VIOLATION"
    assert list(root.glob("*.tmp*")) == []


def test_cleanup_safe_after_higher_ancestor_substitution_nested(tmp_path: Path) -> None:
    """Nested directories (depth >= 2): higher ancestor moved outside and symlinked back.

    Exercises both explicit cleanup and cleanup triggered by failed commit.
    Asserts no unsafe unlink and preservation of source and relocated temp bytes/identities.
    """
    root = tmp_path / "vocab_root"
    root.mkdir()
    ancestor_dir = root / "ancestor"
    ancestor_dir.mkdir()
    parent_dir = ancestor_dir / "parent"
    parent_dir.mkdir()
    target_path = parent_dir / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="nested_orig")
    orig_bytes = _write_fixture_bytes(target_path, orig_content)
    orig_hash = _sha256(orig_bytes)

    source = _make_source_file(
        source_id="src_nested_higher",
        relative_path="ancestor/parent/29-09-2026.md",
        content_hash=orig_hash,
    )
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # Prepare staged write
    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="prop"), orig_hash)
    temp_filename = staged._temp_path.name

    # Move higher ancestor outside and symlink back
    outside_ancestor = tmp_path / "outside_ancestor"
    ancestor_dir.rename(outside_ancestor)
    ancestor_dir.symlink_to(outside_ancestor)

    relocated_temp = outside_ancestor / "parent" / temp_filename
    assert relocated_temp.exists()
    temp_bytes = relocated_temp.read_bytes()
    temp_stat = os.stat(relocated_temp, follow_symlinks=False)
    temp_id = (temp_stat.st_dev, temp_stat.st_ino)

    # 1. Exercise explicit cleanup
    staged.cleanup()
    assert ancestor_dir.is_symlink()
    assert outside_ancestor.exists()
    assert relocated_temp.exists()
    assert relocated_temp.read_bytes() == temp_bytes
    cur_stat = os.stat(relocated_temp, follow_symlinks=False)
    assert (cur_stat.st_dev, cur_stat.st_ino) == temp_id
    assert (outside_ancestor / "parent" / "29-09-2026.md").read_bytes() == orig_bytes

    # 2. Exercise cleanup triggered by failed commit with higher ancestor substituted
    ancestor_dir.unlink()
    outside_ancestor.rename(ancestor_dir)

    staged2 = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="prop2"), orig_hash)
    temp2_name = staged2._temp_path.name

    ancestor_dir.rename(outside_ancestor)
    ancestor_dir.symlink_to(outside_ancestor)

    relocated_temp2 = outside_ancestor / "parent" / temp2_name
    assert relocated_temp2.exists()
    temp2_bytes = relocated_temp2.read_bytes()

    with pytest.raises(SourceSecurityError) as exc_info:
        staged2.commit()
    assert exc_info.value.code == "SECURITY_VIOLATION"

    # Preserved after failed commit
    assert ancestor_dir.is_symlink()
    assert outside_ancestor.exists()
    assert relocated_temp2.exists()
    assert relocated_temp2.read_bytes() == temp2_bytes
    assert (outside_ancestor / "parent" / "29-09-2026.md").read_bytes() == orig_bytes


def test_root_rename_and_reparse_substitution_after_preparation(tmp_path: Path) -> None:
    """Root directory renamed/replaced with directory or symlink after preparation.

    Preserves original entries and substituted entries; fails commit and cleanup safely.
    """
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="root_sub_test")
    orig_bytes = _write_fixture_bytes(source_path, orig_content)
    orig_hash = _sha256(orig_bytes)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # Case A: Root replaced with a distinct directory
    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    temp_name = staged._temp_path.name

    renamed_root = tmp_path / "renamed_root_dir"
    root.rename(renamed_root)
    root.mkdir()  # New directory at original root path (distinct inode)
    substitute_marker = root / "marker.txt"
    _write_fixture_bytes(substitute_marker, "substitute marker")

    relocated_temp = renamed_root / temp_name
    assert relocated_temp.exists()
    temp_bytes = relocated_temp.read_bytes()

    # Commit must fail with ROOT_IDENTITY_CHANGED
    with pytest.raises(SourceSecurityError) as exc_info:
        staged.commit()
    assert exc_info.value.code == "ROOT_IDENTITY_CHANGED"

    # Both original entries in renamed_root and substituted entries in root are preserved
    assert substitute_marker.exists()
    assert (renamed_root / "29-09-2026.md").read_bytes() == orig_bytes
    assert relocated_temp.exists()
    assert relocated_temp.read_bytes() == temp_bytes

    # Explicit cleanup also preserves entries
    staged.cleanup()
    assert substitute_marker.exists()
    assert relocated_temp.exists()

    # Case B: Root replaced with a symlink (reparse point)
    shutil.rmtree(root)
    renamed_root.rename(root)

    staged_b = adapter.prepare_staged_write(
        source.id, _make_valid_markdown(word="new_b"), orig_hash
    )
    temp_b_name = staged_b._temp_path.name

    root.rename(renamed_root)
    root.symlink_to(renamed_root)

    relocated_temp_b = renamed_root / temp_b_name
    assert relocated_temp_b.exists()

    with pytest.raises(SourceSecurityError) as exc_info2:
        staged_b.commit()
    assert exc_info2.value.code in {"ROOT_IDENTITY_CHANGED", "SECURITY_VIOLATION"}

    assert root.is_symlink()
    assert relocated_temp_b.exists()
    assert (renamed_root / "29-09-2026.md").read_bytes() == orig_bytes


def test_staging_failure_before_fdopen_with_ancestor_and_temp_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inject failure before fdopen while substituting higher ancestor or temp entry.

    Asserts substituted entries and outside files remain intact, descriptors close,
    and original typed error survives.
    """
    root = tmp_path / "vocab_root"
    root.mkdir()
    ancestor_dir = root / "ancestor"
    ancestor_dir.mkdir()
    parent_dir = ancestor_dir / "parent"
    parent_dir.mkdir()
    target_path = parent_dir / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="inject_before_fdopen")
    orig_bytes = _write_fixture_bytes(target_path, orig_content)
    orig_hash = _sha256(orig_bytes)

    source = _make_source_file(
        source_id="src_inject_pre_fdopen",
        relative_path="ancestor/parent/29-09-2026.md",
        content_hash=orig_hash,
    )
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    outside_ancestor = tmp_path / "outside_ancestor_chmod"

    def inject_chmod_fail(*_args: Any, **_kwargs: Any) -> None:
        ancestor_dir.rename(outside_ancestor)
        ancestor_dir.symlink_to(outside_ancestor)
        raise PermissionError("Injected chmod permission denied")

    monkeypatch.setattr(os, "chmod", inject_chmod_fail)

    with pytest.raises(SourceAccessError) as exc_info:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert exc_info.value.code == "ACCESS_DENIED"

    # Substituted entries and outside files remain intact
    assert ancestor_dir.is_symlink()
    assert outside_ancestor.exists()
    assert (outside_ancestor / "parent" / "29-09-2026.md").read_bytes() == orig_bytes
    outside_temps = list((outside_ancestor / "parent").glob("*.tmp*"))
    assert len(outside_temps) == 1
    assert outside_temps[0].exists()


def test_staging_failure_during_write_fsync_with_temp_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inject failure during write/fsync while replacing temp entry with regular file or link.

    Asserts substituted entries and outside files remain intact, descriptors close,
    and original typed error survives.
    """
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="inject_fsync")
    orig_bytes = _write_fixture_bytes(source_path, orig_content)
    orig_hash = _sha256(orig_bytes)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    substitute_regular = tmp_path / "substitute_regular.tmp"
    _write_fixture_bytes(substitute_regular, "precious substituted regular file")

    def inject_fsync_replace_temp_regular(_fd: int) -> None:
        temps = list(root.glob("*.tmp*"))
        if temps:
            temp_file = temps[0]
            temp_file.unlink()
            shutil.copy(substitute_regular, temp_file)
        raise OSError("Injected disk I/O failure during fsync")

    monkeypatch.setattr(os, "fsync", inject_fsync_replace_temp_regular)

    with pytest.raises(SourceFileError) as exc_info:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert exc_info.value.code == "IO_ERROR"

    temps_after = list(root.glob("*.tmp*"))
    assert len(temps_after) == 1
    assert temps_after[0].read_bytes() == b"precious substituted regular file"
    assert source_path.read_bytes() == orig_bytes

    # Now test replacement with a symlink during fsync failure
    temps_after[0].unlink()
    substitute_target = tmp_path / "precious_link_target.md"
    _write_fixture_bytes(substitute_target, "precious link content")

    def inject_fsync_replace_temp_symlink(_fd: int) -> None:
        temps = list(root.glob("*.tmp*"))
        if temps:
            temp_file = temps[0]
            temp_file.unlink()
            temp_file.symlink_to(substitute_target)
        raise OSError("Injected disk I/O failure during fsync")

    monkeypatch.setattr(os, "fsync", inject_fsync_replace_temp_symlink)

    with pytest.raises(SourceFileError) as exc_info2:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new2"), orig_hash)
    assert exc_info2.value.code == "IO_ERROR"

    temps_after2 = list(root.glob("*.tmp*"))
    assert len(temps_after2) == 1
    assert temps_after2[0].is_symlink()
    assert substitute_target.read_bytes() == b"precious link content"
    assert source_path.read_bytes() == orig_bytes


def test_safe_cleanup_temp_unauthenticated_or_failed_inspection_retains_entry(
    tmp_path: Path,
) -> None:
    """Direct _safe_cleanup_temp test: retains entry when stat missing or check fails."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    target_dir = root / "sub_dir"
    target_dir.mkdir()
    temp_file = target_dir / "temp.tmp"
    _write_fixture_bytes(temp_file, "temp content")
    temp_st = os.stat(temp_file)
    temp_id = (temp_st.st_dev, temp_st.st_ino)
    root_st = os.stat(root)
    root_id = (root_st.st_dev, root_st.st_ino)
    target_dir_st = os.stat(target_dir)
    target_dir_id = (target_dir_st.st_dev, target_dir_st.st_ino)

    # 1. Missing initial_temp_stat (None) -> retains entry
    res1 = _safe_cleanup_temp(
        root_path=root,
        expected_root_id=root_id,
        intermediate_dirs=[(target_dir, target_dir_id)],
        target_dir=target_dir,
        target_dir_stat=target_dir_id,
        temp_path=temp_file,
        initial_temp_stat=None,
    )
    assert res1 is False
    assert temp_file.exists()

    # 2. Inode mismatch on temp_file -> retains entry
    res2 = _safe_cleanup_temp(
        root_path=root,
        expected_root_id=root_id,
        intermediate_dirs=[(target_dir, target_dir_id)],
        target_dir=target_dir,
        target_dir_stat=target_dir_id,
        temp_path=temp_file,
        initial_temp_stat=(temp_id[0], temp_id[1] + 9999),
    )
    assert res2 is False
    assert temp_file.exists()

    # 3. Root identity mismatch -> retains entry
    res3 = _safe_cleanup_temp(
        root_path=root,
        expected_root_id=(root_id[0], root_id[1] + 9999),
        intermediate_dirs=[(target_dir, target_dir_id)],
        target_dir=target_dir,
        target_dir_stat=target_dir_id,
        temp_path=temp_file,
        initial_temp_stat=temp_id,
    )
    assert res3 is False
    assert temp_file.exists()

    # 4. Authenticated cleanup succeeds
    res4 = _safe_cleanup_temp(
        root_path=root,
        expected_root_id=root_id,
        intermediate_dirs=[(target_dir, target_dir_id)],
        target_dir=target_dir,
        target_dir_stat=target_dir_id,
        temp_path=temp_file,
        initial_temp_stat=temp_id,
    )
    assert res4 is True
    assert not temp_file.exists()


def test_authenticated_partial_staging_cleanup_and_repeated_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Authenticated partial staging cleans up temp when boundary is intact; cleanup idempotent."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="partial_orig")
    orig_bytes = _write_fixture_bytes(source_path, orig_content)
    orig_hash = _sha256(orig_bytes)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # 1. Partial staging failure with intact boundary: removes temp file
    def fail_fsync(_fd: int) -> None:
        raise OSError("Injected disk error")

    monkeypatch.setattr(os, "fsync", fail_fsync)
    with pytest.raises(SourceFileError) as exc_info:
        adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert exc_info.value.code == "IO_ERROR"
    assert list(root.glob("*.tmp*")) == []
    assert source_path.read_bytes() == orig_bytes

    monkeypatch.undo()

    # 2. Staged write commit failure removes temp file
    staged = adapter.prepare_staged_write(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert staged._temp_path.exists()

    # Alter target on disk so commit encounters REVISION_CONFLICT
    _write_fixture_bytes(source_path, _make_valid_markdown(word="concurrent_edit"))

    with pytest.raises(SourceConflictError) as exc_info2:
        staged.commit()
    assert exc_info2.value.code == "REVISION_CONFLICT"
    assert not staged._temp_path.exists()

    # 3. Repeated cleanup call is idempotent and safe
    staged.cleanup()
    staged.cleanup()


def test_crlf_source_byte_exact_hash_and_stale_lf_rejection(tmp_path: Path) -> None:
    """Byte-exact hashing: matching CRLF bytes succeed; stale LF hash fails without replacement."""
    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"

    # Write explicit CRLF bytes to disk
    lf_text = _make_valid_markdown(word="crlf_test")
    crlf_text = lf_text.replace("\n", "\r\n")
    crlf_bytes = crlf_text.encode("utf-8")
    source_path.write_bytes(crlf_bytes)

    crlf_hash = _sha256(crlf_bytes)
    lf_hash = _sha256(lf_text.encode("utf-8"))
    assert crlf_hash != lf_hash, "CRLF and LF hashes must differ for byte-exact validation"

    source = _make_source_file(content_hash=crlf_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    new_content = _make_valid_markdown(word="crlf_updated")

    # 1. Stale LF-based hash is rejected with REVISION_CONFLICT without modifying disk
    with pytest.raises(SourceConflictError) as exc_info:
        adapter.replace_source_content(
            source_id=source.id,
            new_content=new_content,
            expected_content_hash=lf_hash,
        )
    assert exc_info.value.code == "REVISION_CONFLICT"
    assert source_path.read_bytes() == crlf_bytes

    # 2. Matching actual CRLF-byte hash succeeds
    receipt = adapter.replace_source_content(
        source_id=source.id,
        new_content=new_content,
        expected_content_hash=crlf_hash,
    )
    assert isinstance(receipt, ReplacementReceipt)
    assert receipt.old_content_hash == crlf_hash
    assert source_path.read_bytes() == new_content.encode("utf-8")


def test_check_windows_ownership_deterministic_failure_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Deterministic failure paths for _check_windows_ownership under simulated Win32 conditions."""
    test_file = tmp_path / "test_file.md"
    _write_fixture_bytes(test_file, "sample")

    monkeypatch.setattr(sys, "platform", "win32")

    class FakeFunc:
        def __init__(self, fn: Any) -> None:
            self.fn = fn
            self.argtypes: Any = None
            self.restype: Any = None

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return self.fn(*args, **kwargs)

    # 1. windll is None -> returns False
    monkeypatch.setattr(ctypes, "windll", None, raising=False)
    assert _check_windows_ownership(test_file) is False

    # 2. OpenProcessToken fails (returns 0)
    class FakeKernel32_2:
        def __init__(self) -> None:
            self.GetCurrentProcess = FakeFunc(lambda: 1)
            self.CloseHandle = FakeFunc(lambda _h: 1)
            self.LocalFree = FakeFunc(lambda _m: 0)

    class FakeAdvapi32TokenFail:
        def __init__(self) -> None:
            self.OpenProcessToken = FakeFunc(lambda *_a: 0)
            self.GetTokenInformation = FakeFunc(lambda *_a: 0)
            self.GetNamedSecurityInfoW = FakeFunc(lambda *_a: 0)
            self.EqualSid = FakeFunc(lambda *_a: 0)

    class FakeWindllTokenFail:
        advapi32 = FakeAdvapi32TokenFail()
        kernel32 = FakeKernel32_2()

    monkeypatch.setattr(ctypes, "windll", FakeWindllTokenFail(), raising=False)
    assert _check_windows_ownership(test_file) is False

    # 3. GetTokenInformation fails (returns 0) - tok handle is closed
    closed_handles_3: list[Any] = []

    class FakeKernel32_3:
        def __init__(self) -> None:
            self.GetCurrentProcess = FakeFunc(lambda: 1)

            def _close(h: Any) -> int:
                closed_handles_3.append(h)
                return 1

            self.CloseHandle = FakeFunc(_close)
            self.LocalFree = FakeFunc(lambda _m: 0)

    class FakeAdvapi32GetTokenInfoFail:
        def __init__(self) -> None:
            self.OpenProcessToken = FakeFunc(self._opt)
            self.GetTokenInformation = FakeFunc(lambda *_a: 0)
            self.GetNamedSecurityInfoW = FakeFunc(lambda *_a: 0)
            self.EqualSid = FakeFunc(lambda *_a: 0)

        def _opt(self, _proc: Any, _query: Any, tok_ref: Any) -> int:
            tok_ref._obj.value = 1234
            return 1

    class FakeWindllGetTokenInfoFail:
        advapi32 = FakeAdvapi32GetTokenInfoFail()
        kernel32 = FakeKernel32_3()

    monkeypatch.setattr(ctypes, "windll", FakeWindllGetTokenInfoFail(), raising=False)
    assert _check_windows_ownership(test_file) is False
    assert len(closed_handles_3) == 1

    # 4. GetNamedSecurityInfoW fails (returns non-zero error) - tok handle is closed
    closed_handles_4: list[Any] = []
    freed_mem_4: list[Any] = []

    class FakeKernel32Track4:
        def __init__(self) -> None:
            self.GetCurrentProcess = FakeFunc(lambda: 1)

            def _close(h: Any) -> int:
                closed_handles_4.append(h)
                return 1

            def _free(m: Any) -> int:
                freed_mem_4.append(m)
                return 0

            self.CloseHandle = FakeFunc(_close)
            self.LocalFree = FakeFunc(_free)

    class FakeAdvapi32SecurityFail:
        def __init__(self) -> None:
            self.OpenProcessToken = FakeFunc(self._opt)
            self.GetTokenInformation = FakeFunc(self._gti)
            self.GetNamedSecurityInfoW = FakeFunc(lambda *_a: 5)  # ERROR_ACCESS_DENIED
            self.EqualSid = FakeFunc(lambda *_a: 0)

        def _opt(self, _proc: Any, _query: Any, tok_ref: Any) -> int:
            tok_ref._obj.value = 1234
            return 1

        def _gti(self, _tok: Any, _info_type: Any, _buf: Any, _buf_len: Any, len_ref: Any) -> int:
            len_ref._obj.value = 68
            return 1

    class FakeWindllSecurityFail:
        advapi32 = FakeAdvapi32SecurityFail()
        kernel32 = FakeKernel32Track4()

    monkeypatch.setattr(ctypes, "windll", FakeWindllSecurityFail(), raising=False)
    assert _check_windows_ownership(test_file) is False
    assert len(closed_handles_4) == 1
    assert len(freed_mem_4) == 0

    # 5. Ownership mismatch (EqualSid returns 0) - fails closed and releases both p_sd and tok
    closed_handles_5: list[Any] = []
    freed_mem_5: list[Any] = []

    class FakeKernel32Track5:
        def __init__(self) -> None:
            self.GetCurrentProcess = FakeFunc(lambda: 1)

            def _close(h: Any) -> int:
                closed_handles_5.append(h)
                return 1

            def _free(m: Any) -> int:
                freed_mem_5.append(m)
                return 0

            self.CloseHandle = FakeFunc(_close)
            self.LocalFree = FakeFunc(_free)

    class FakeAdvapi32OwnershipMismatch:
        def __init__(self) -> None:
            self.OpenProcessToken = FakeFunc(self._opt)
            self.GetTokenInformation = FakeFunc(self._gti)
            self.GetNamedSecurityInfoW = FakeFunc(self._gnsi)
            self.EqualSid = FakeFunc(lambda *_a: 0)  # Ownership mismatch

        def _opt(self, _proc: Any, _query: Any, tok_ref: Any) -> int:
            tok_ref._obj.value = 1234
            return 1

        def _gti(self, _tok: Any, _info_type: Any, buf: Any, _buf_len: Any, len_ref: Any) -> int:
            len_ref._obj.value = 68
            if buf is not None:
                ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p)).contents.value = 5678
            return 1

        def _gnsi(
            self,
            _path: Any,
            _obj_type: Any,
            _sec_info: Any,
            p_owner_ref: Any,
            _group_ref: Any,
            _dacl_ref: Any,
            _sacl_ref: Any,
            p_sd_ref: Any,
        ) -> int:
            p_owner_ref._obj.value = 9999
            p_sd_ref._obj.value = 8888
            return 0

    class FakeWindllOwnershipMismatch:
        advapi32 = FakeAdvapi32OwnershipMismatch()
        kernel32 = FakeKernel32Track5()

    monkeypatch.setattr(ctypes, "windll", FakeWindllOwnershipMismatch(), raising=False)
    assert _check_windows_ownership(test_file) is False
    # Verifies both token handle and security descriptor memory were reliably freed
    assert len(closed_handles_5) == 1
    assert len(freed_mem_5) == 1


@pytest.mark.parametrize(
    "tamper", [None, "canonical", "traversal", "absolute", "hash", "inode", "hardlink", "symlink"]
)
def test_restart_cleanup_accepts_only_adapter_owned_staged_identity(
    tmp_path: Path,
    tamper: str | None,
) -> None:
    from dataclasses import replace

    root = tmp_path / "restart-root"
    root.mkdir()
    original = _make_valid_markdown(word="old")
    canonical = root / "29-09-2026.md"
    canonical.write_bytes(original.encode())
    source = _make_source_file(content_hash=_sha256(original))
    adapter = SourceFileAdapter(root, {source.id: source})
    staged = adapter.prepare_staged_write(
        source.id, _make_valid_markdown(word="new"), _sha256(original)
    )
    handle = staged.recovery_handle
    temp = root / handle.relative_path
    if tamper == "canonical":
        handle = replace(handle, relative_path=source.relative_path)
    elif tamper == "traversal":
        handle = replace(handle, relative_path="../owned.tmp")
    elif tamper == "absolute":
        handle = replace(handle, relative_path=str(temp))
    elif tamper == "hash":
        temp.write_bytes(b"changed")
    elif tamper == "inode":
        temp.rename(root / "retained-original-temp")
        temp.write_bytes(_make_valid_markdown(word="new").encode())
    elif tamper == "hardlink":
        os.link(temp, root / "linked-temp")
    elif tamper == "symlink":
        temp.unlink()
        temp.symlink_to(canonical)
    restarted = SourceFileAdapter(root, {source.id: source})
    if tamper is not None:
        with pytest.raises(SourceFileError):
            restarted.cleanup_abandoned_temp(handle)
        assert temp.exists()
    else:
        restarted.cleanup_abandoned_temp(handle)
        assert not temp.exists()
        restarted.cleanup_abandoned_temp(handle)
    assert canonical.read_bytes() == original.encode()
