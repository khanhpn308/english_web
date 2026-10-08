"""Synthetic host-only T090 edit-interface tests; no provider security claims."""

import hashlib
from pathlib import Path

import pytest
from tools.orchestrator.worker_sandbox import (
    HostEditRejected,
    ProposedTextEdit,
    apply_host_text_edit,
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fixture(tmp_path: Path) -> tuple[Path, bytes]:
    (tmp_path / "src").mkdir()
    old = b"original\n"
    (tmp_path / "src" / "ok.py").write_bytes(old)
    (tmp_path / "private.txt").write_text("protected", encoding="utf-8")
    return tmp_path, old


def test_host_permits_pinned_edit_and_returns_digest(tmp_path: Path) -> None:
    root, original = fixture(tmp_path)
    replacement = "print('accepted')\n"
    result = apply_host_text_edit(
        root,
        {"src/ok.py"},
        ProposedTextEdit("src/ok.py", sha(original), replacement),
    )
    assert (root / "src/ok.py").read_text() == replacement
    assert result.before_sha256 == sha(original)
    assert result.after_sha256 == sha(replacement.encode())
    assert (root / "private.txt").read_text() == "protected"


def test_host_can_create_only_explicitly_allowlisted_path(tmp_path: Path) -> None:
    root, _ = fixture(tmp_path)
    result = apply_host_text_edit(
        root, {"src/new.py"}, ProposedTextEdit("src/new.py", None, "answer = 42\n")
    )
    assert result.before_sha256 is None
    assert (root / "src/new.py").read_text() == "answer = 42\n"


@pytest.mark.parametrize(
    "path",
    [
        "../private.txt",
        "src/../../private.txt",
        "src/../private.txt",
        "src/./ok.py",
        "src//ok.py",
        "src/ok.py/",
        "/etc/passwd",
        "C:/unsafe.py",
        "src\\ok.py",
        "src/ok.py\x00ignored",
        "",
    ],
)
def test_host_rejects_noncanonical_paths_without_writes(tmp_path: Path, path: str) -> None:
    root, original = fixture(tmp_path)
    with pytest.raises(HostEditRejected):
        apply_host_text_edit(
            root, {"src/ok.py"}, ProposedTextEdit(path, sha(original), "changed")
        )
    assert (root / "src/ok.py").read_bytes() == original


def test_host_rejects_path_outside_allowlist_even_with_valid_sha(tmp_path: Path) -> None:
    root, original = fixture(tmp_path)
    with pytest.raises(HostEditRejected, match="allowlist"):
        apply_host_text_edit(
            root,
            {"src/ok.py"},
            ProposedTextEdit("private.txt", sha(b"protected"), "changed"),
        )
    assert (root / "private.txt").read_text() == "protected"
    assert (root / "src/ok.py").read_bytes() == original


def test_host_rejects_stale_sha(tmp_path: Path) -> None:
    root, original = fixture(tmp_path)
    with pytest.raises(HostEditRejected, match="preimage"):
        apply_host_text_edit(
            root, {"src/ok.py"}, ProposedTextEdit("src/ok.py", sha(b"stale"), "changed")
        )
    assert (root / "src/ok.py").read_bytes() == original


def test_host_rejects_invalid_preimage_format(tmp_path: Path) -> None:
    root, original = fixture(tmp_path)
    with pytest.raises(HostEditRejected, match="digest"):
        apply_host_text_edit(
            root, {"src/ok.py"}, ProposedTextEdit("src/ok.py", "BAD", "changed")
        )
    assert (root / "src/ok.py").read_bytes() == original


@pytest.mark.parametrize("content", ["\x00", "x" * (256 * 1024 + 1)])
def test_host_rejects_binary_or_oversized_text(tmp_path: Path, content: str) -> None:
    root, original = fixture(tmp_path)
    with pytest.raises(HostEditRejected, match="size/text"):
        apply_host_text_edit(
            root, {"src/ok.py"}, ProposedTextEdit("src/ok.py", sha(original), content)
        )
    assert (root / "src/ok.py").read_bytes() == original


def test_host_rejects_leaf_symlink(tmp_path: Path) -> None:
    root, _ = fixture(tmp_path)
    (root / "src" / "outside.py").symlink_to(root / "private.txt")
    with pytest.raises(HostEditRejected, match="destination"):
        apply_host_text_edit(
            root, {"src/outside.py"}, ProposedTextEdit("src/outside.py", None, "changed")
        )
    assert (root / "private.txt").read_text() == "protected"


def test_host_rejects_symlinked_ancestor(tmp_path: Path) -> None:
    root, _ = fixture(tmp_path)
    (root / "alias").symlink_to(root / "src", target_is_directory=True)
    with pytest.raises(HostEditRejected, match="ancestor"):
        apply_host_text_edit(
            root, {"alias/ok.py"}, ProposedTextEdit("alias/ok.py", None, "changed")
        )
    assert (root / "src/ok.py").read_text() == "original\n"


def test_host_rejects_missing_preimage_for_existing_file(tmp_path: Path) -> None:
    root, original = fixture(tmp_path)
    with pytest.raises(HostEditRejected, match="preimage"):
        apply_host_text_edit(
            root, {"src/ok.py"}, ProposedTextEdit("src/ok.py", None, "changed")
        )
    assert (root / "src/ok.py").read_bytes() == original


def test_host_does_not_accept_its_allowlist_from_edit_path_prefix(tmp_path: Path) -> None:
    root, original = fixture(tmp_path)
    (root / "src-evil").mkdir()
    (root / "src-evil" / "ok.py").write_bytes(original)
    with pytest.raises(HostEditRejected, match="allowlist"):
        apply_host_text_edit(
            root, {"src/ok.py"}, ProposedTextEdit("src-evil/ok.py", sha(original), "bad")
        )
    assert (root / "src-evil" / "ok.py").read_bytes() == original
