"""Windows-native source path and security descriptor verification tests (T021).

Verification scope:
1. NTFS junctions and reparse point rejection.
2. NTFS hardlink rejection (st_nlink > 1).
3. Root rename, substitution, and volume identity changes.
4. Post-prepare ancestor substitution on Windows.
5. Windows read-only attribute (FILE_ATTRIBUTE_READONLY) access denial.
6. Windows process token user SID, file owner SID, and DACL verification via advapi32.
7. Durability of atomic replacement (os.replace via MoveFileExW) on NTFS.
8. Privacy: no raw Windows paths, content sentinels, SIDs, or account names in logs/errors.

Truthful verification discipline:
Without an existing owner-approved exception permitting skips, missing native Windows capability
must produce an explicit sanitized unavailable/failure outcome and BLOCKED/PENDING handoff.
Platform capability guard: owner: T021; expiry: 2026-12-31;
compensating check: portable unit tests in backend/tests/test_source_files.py.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from backend.app.adapters.source_files import (
    ReplacementReceipt,
    SourceAccessError,
    SourceConflictError,
    SourceFileAdapter,
    SourceSecurityError,
    _check_windows_ownership,
    _is_reparse_or_link,
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
    source_id: str = "src_win_29_09_2026",
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


def _write_fixture_bytes(path: Path, text: str) -> bytes:
    """Write fixture text with explicit UTF-8 bytes and disabled newline translation."""
    data = text.encode("utf-8")
    path.write_bytes(data)
    return data


def _sha256(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


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


def _require_native_windows() -> None:
    """Fail explicitly when native Windows capability is unavailable.

    Prevents silent pass / false green on Linux/POSIX hosts.
    Platform capability guard: owner: T021; expiry: 2026-12-31;
    compensating check: portable unit tests in backend/tests/test_source_files.py.
    """
    if sys.platform != "win32":
        pytest.fail(
            "Native Windows runtime unavailable: platform is linux "
            "(PENDING genuine Windows environment; acceptance criteria fail closed)"
        )


def _inspect_windows_security_info(path: Path) -> dict[str, bool]:
    """Retrieve owner SID and DACL security info via Win32 advapi32.

    Returns categorical verification flags without exposing raw SIDs,
    account names, descriptors, or paths.
    """
    _require_native_windows()
    windll: Any = getattr(ctypes, "windll", None)
    if windll is None:
        return {
            "api_available": False,
            "api_success": False,
            "owner_matched": False,
            "dacl_present": False,
            "dacl_valid": False,
        }

    advapi32 = windll.advapi32
    kernel32 = windll.kernel32

    # 64-bit ctypes declarations
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p

    advapi32.OpenProcessToken.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.OpenProcessToken.restype = ctypes.c_int
    advapi32.GetTokenInformation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    advapi32.GetTokenInformation.restype = ctypes.c_int

    advapi32.GetNamedSecurityInfoW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.GetNamedSecurityInfoW.restype = ctypes.c_ulong

    advapi32.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    advapi32.EqualSid.restype = ctypes.c_int

    advapi32.IsValidAcl.argtypes = [ctypes.c_void_p]
    advapi32.IsValidAcl.restype = ctypes.c_int

    owner_info = 0x00000001
    dacl_info = 0x00000004
    se_file_object = 1
    token_query = 8
    token_user_type = 1

    proc = kernel32.GetCurrentProcess()
    tok = ctypes.c_void_p()
    if not advapi32.OpenProcessToken(proc, token_query, ctypes.byref(tok)) or not tok:
        return {
            "api_available": True,
            "api_success": False,
            "owner_matched": False,
            "dacl_present": False,
            "dacl_valid": False,
        }

    try:
        buf_len = ctypes.c_ulong(0)
        advapi32.GetTokenInformation(tok, token_user_type, None, 0, ctypes.byref(buf_len))
        if buf_len.value == 0:
            return {
                "api_available": True,
                "api_success": False,
                "owner_matched": False,
                "dacl_present": False,
                "dacl_valid": False,
            }

        buf = ctypes.create_string_buffer(buf_len.value)
        if not advapi32.GetTokenInformation(
            tok, token_user_type, buf, buf_len.value, ctypes.byref(buf_len)
        ):
            return {
                "api_available": True,
                "api_success": False,
                "owner_matched": False,
                "dacl_present": False,
                "dacl_valid": False,
            }

        user_sid = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p)).contents
        p_owner = ctypes.c_void_p()
        p_dacl = ctypes.c_void_p()
        p_sd = ctypes.c_void_p()

        res = advapi32.GetNamedSecurityInfoW(
            str(path),
            se_file_object,
            owner_info | dacl_info,
            ctypes.byref(p_owner),
            None,
            ctypes.byref(p_dacl),
            None,
            ctypes.byref(p_sd),
        )
        if res != 0 or not p_sd:
            return {
                "api_available": True,
                "api_success": False,
                "owner_matched": False,
                "dacl_present": False,
                "dacl_valid": False,
            }

        try:
            owner_matched = bool(p_owner and advapi32.EqualSid(user_sid, p_owner))
            dacl_present = bool(p_dacl)
            dacl_valid = bool(p_dacl and advapi32.IsValidAcl(p_dacl))
            return {
                "api_available": True,
                "api_success": True,
                "owner_matched": owner_matched,
                "dacl_present": dacl_present,
                "dacl_valid": dacl_valid,
            }
        finally:
            kernel32.LocalFree(p_sd)
    finally:
        kernel32.CloseHandle(tok)


def test_windows_junction_rejection(tmp_path: Path) -> None:
    """NTFS directory junction is rejected with SECURITY_VIOLATION.

    Fails explicitly if native Windows is unavailable or if junction creation fails.
    """
    _require_native_windows()

    root = tmp_path / "vocab_root"
    root.mkdir()
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    target_file = outside_dir / "29-09-2026.md"
    content = _make_valid_markdown(word="junction_target")
    orig_bytes = _write_fixture_bytes(target_file, content)
    content_hash = _sha256(orig_bytes)

    junction_dir = root / "sub_junction"
    # Create NTFS junction via cmd mklink /J
    cmd = ["cmd.exe", "/c", "mklink", "/J", str(junction_dir), str(outside_dir)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        pytest.fail("Failed to create NTFS junction fixture (subprocess exited non-zero)")

    source = _make_source_file(
        relative_path="sub_junction/29-09-2026.md", content_hash=content_hash
    )
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    with pytest.raises(SourceSecurityError) as exc_info:
        adapter.replace_source_content(source.id, _make_valid_markdown(word="attack"), content_hash)
    assert exc_info.value.code == "SECURITY_VIOLATION"
    assert target_file.read_bytes() == orig_bytes


def test_windows_reparse_attribute_detection(tmp_path: Path) -> None:
    """Helper _is_reparse_or_link detects FILE_ATTRIBUTE_REPARSE_POINT on Windows.

    Must run on native Windows to test Win32 file attribute detection.
    """
    _require_native_windows()

    test_file = tmp_path / "test_reparse.md"
    _write_fixture_bytes(test_file, "sample")
    st = os.stat(test_file, follow_symlinks=False)
    # Regular file should not have reparse point attribute
    assert _is_reparse_or_link(test_file, st) is False


def test_windows_hardlink_rejection(tmp_path: Path) -> None:
    """NTFS hardlink (st_nlink > 1) is rejected with SECURITY_VIOLATION."""
    _require_native_windows()

    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="hardlinked_win")
    orig_bytes = _write_fixture_bytes(source_path, orig_content)
    orig_hash = _sha256(orig_bytes)

    other_link = tmp_path / "other_link.md"
    os.link(source_path, other_link)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    with pytest.raises(SourceSecurityError) as exc_info:
        adapter.replace_source_content(source.id, _make_valid_markdown(word="hacked"), orig_hash)
    assert exc_info.value.code == "SECURITY_VIOLATION"
    assert source_path.read_bytes() == orig_bytes


def test_windows_root_rename_and_substitution(tmp_path: Path) -> None:
    """Renaming the root directory on Windows triggers ROOT_IDENTITY_CHANGED."""
    _require_native_windows()

    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    orig_bytes = _write_fixture_bytes(source_path, orig_content)
    orig_hash = _sha256(orig_bytes)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # Rename root and substitute with new directory
    renamed_root = tmp_path / "vocab_root_renamed"
    root.rename(renamed_root)
    root.mkdir()

    with pytest.raises(SourceSecurityError) as exc_info:
        adapter.replace_source_content(source.id, _make_valid_markdown(word="new"), orig_hash)
    assert exc_info.value.code == "ROOT_IDENTITY_CHANGED"


def test_windows_ancestor_substitution_rejection(tmp_path: Path) -> None:
    """Prepare -> substitute higher ancestor on NTFS -> commit fails closed; cleanup preserves."""
    _require_native_windows()

    root = tmp_path / "vocab_root"
    root.mkdir()
    higher_dir = root / "higher_dir"
    higher_dir.mkdir()
    immediate_dir = higher_dir / "immediate_dir"
    immediate_dir.mkdir()
    target_path = immediate_dir / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="outside_original")
    orig_bytes = _write_fixture_bytes(target_path, orig_content)
    orig_hash = _sha256(orig_bytes)

    source = _make_source_file(
        relative_path="higher_dir/immediate_dir/29-09-2026.md",
        content_hash=orig_hash,
    )
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    staged = adapter.prepare_staged_write(
        source.id,
        _make_valid_markdown(word="injected_payload"),
        orig_hash,
    )

    outside_dir = tmp_path / "outside_higher"
    higher_dir.rename(outside_dir)

    # Re-link higher ancestor via NTFS junction
    cmd = ["cmd.exe", "/c", "mklink", "/J", str(higher_dir), str(outside_dir)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        pytest.fail("Failed to create NTFS junction fixture (subprocess exited non-zero)")

    with pytest.raises(SourceSecurityError) as exc_info:
        staged.commit()
    assert exc_info.value.code == "SECURITY_VIOLATION"

    # Outside file and relocated staged temp are preserved
    outside_file = outside_dir / "immediate_dir" / "29-09-2026.md"
    assert outside_file.read_bytes() == orig_bytes

    outside_temp = outside_dir / "immediate_dir" / staged._temp_path.name
    assert outside_temp.exists()

    # Explicit cleanup also fails closed and retains outside temp
    staged.cleanup()
    assert outside_temp.exists()


def test_windows_readonly_file_attribute_rejection(tmp_path: Path) -> None:
    """FILE_ATTRIBUTE_READONLY target file fails with ACCESS_DENIED."""
    _require_native_windows()

    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown()
    orig_bytes = _write_fixture_bytes(source_path, orig_content)
    orig_hash = _sha256(orig_bytes)

    windll: Any = getattr(ctypes, "windll", None)
    if windll is None:
        pytest.fail("Windows ctypes.windll is unavailable")

    # Set FILE_ATTRIBUTE_READONLY (0x01)
    file_attribute_readonly = 0x01
    set_res = windll.kernel32.SetFileAttributesW(str(source_path), file_attribute_readonly)
    if set_res == 0:
        pytest.fail("SetFileAttributesW failed to set FILE_ATTRIBUTE_READONLY")

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    try:
        with pytest.raises(SourceAccessError) as exc_info:
            adapter.replace_source_content(
                source.id, _make_valid_markdown(word="blocked"), orig_hash
            )
        assert exc_info.value.code == "ACCESS_DENIED"
    finally:
        # Restore normal attribute (0x80)
        file_attribute_normal = 0x80
        windll.kernel32.SetFileAttributesW(str(source_path), file_attribute_normal)


def test_windows_atomic_replacement_durability(tmp_path: Path) -> None:
    """Verify os.replace on NTFS atomically updates target file contents."""
    _require_native_windows()

    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="initial_ntfs")
    orig_bytes = _write_fixture_bytes(source_path, orig_content)
    orig_hash = _sha256(orig_bytes)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    new_content = _make_valid_markdown(word="updated_ntfs")
    new_bytes = new_content.encode("utf-8")
    receipt = adapter.replace_source_content(source.id, new_content, orig_hash)

    assert isinstance(receipt, ReplacementReceipt)
    assert source_path.read_bytes() == new_bytes
    assert list(root.glob("*.tmp*")) == []


def test_windows_ownership_and_dacl_verification(tmp_path: Path) -> None:
    """Verify Win32 token ownership and DACL retrieval succeed and record categorical evidence."""
    _require_native_windows()

    root = tmp_path / "vocab_root"
    root.mkdir()
    target_file = root / "29-09-2026.md"
    orig_content = _make_valid_markdown(word="dacl_verify")
    orig_bytes = _write_fixture_bytes(target_file, orig_content)
    orig_hash = _sha256(orig_bytes)

    source = _make_source_file(content_hash=orig_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    # 1. Target file security inspection before staging
    target_sec = _inspect_windows_security_info(target_file)
    assert target_sec["api_success"] is True
    assert target_sec["owner_matched"] is True
    assert target_sec["dacl_present"] is True
    assert target_sec["dacl_valid"] is True
    assert _check_windows_ownership(target_file) is True

    # 2. Inspect staged temporary file
    staged = adapter.prepare_staged_write(
        source.id,
        _make_valid_markdown(word="dacl_updated"),
        orig_hash,
    )
    temp_sec = _inspect_windows_security_info(staged._temp_path)
    assert temp_sec["api_success"] is True
    assert temp_sec["owner_matched"] is True
    assert temp_sec["dacl_present"] is True
    assert temp_sec["dacl_valid"] is True

    # 3. Commit and inspect replaced target
    receipt = staged.commit()
    assert isinstance(receipt, ReplacementReceipt)
    replaced_sec = _inspect_windows_security_info(target_file)
    assert replaced_sec["api_success"] is True
    assert replaced_sec["owner_matched"] is True
    assert replaced_sec["dacl_present"] is True
    assert replaced_sec["dacl_valid"] is True


def test_windows_crlf_source_byte_exact_hash_and_stale_lf_rejection(tmp_path: Path) -> None:
    """Byte-exact hashing on Windows: CRLF disk bytes match; stale LF hash fails closed."""
    _require_native_windows()

    root = tmp_path / "vocab_root"
    root.mkdir()
    source_path = root / "29-09-2026.md"

    # Write explicit CRLF bytes to disk
    lf_text = _make_valid_markdown(word="crlf_win_test")
    crlf_text = lf_text.replace("\n", "\r\n")
    crlf_bytes = crlf_text.encode("utf-8")
    source_path.write_bytes(crlf_bytes)

    crlf_hash = _sha256(crlf_bytes)
    lf_hash = _sha256(lf_text.encode("utf-8"))
    assert crlf_hash != lf_hash, "CRLF and LF hashes must differ for byte-exact validation"

    source = _make_source_file(content_hash=crlf_hash)
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    new_content = _make_valid_markdown(word="crlf_win_updated")

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


def test_windows_ownership_and_dacl_deterministic_failure_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deterministic failure paths for Win32 security info and token DACL inspection."""
    _require_native_windows()

    test_file = tmp_path / "test_sec.md"
    _write_fixture_bytes(test_file, "sample")

    class FakeFunc:
        def __init__(self, fn: Any) -> None:
            self.fn = fn
            self.argtypes: Any = None
            self.restype: Any = None

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return self.fn(*args, **kwargs)

    # 1. API unavailable
    monkeypatch.setattr(ctypes, "windll", None, raising=False)
    res1 = _inspect_windows_security_info(test_file)
    assert res1["api_available"] is False
    assert res1["api_success"] is False

    # 2. Token query failure
    closed_2: list[Any] = []

    class FakeKernel_2:
        def __init__(self) -> None:
            self.GetCurrentProcess = FakeFunc(lambda: 1)

            def _close(h: Any) -> int:
                closed_2.append(h)
                return 1

            self.CloseHandle = FakeFunc(_close)
            self.LocalFree = FakeFunc(lambda _m: 0)

    class FakeAdvapi_2:
        def __init__(self) -> None:
            self.OpenProcessToken = FakeFunc(lambda *_a: 0)
            self.GetTokenInformation = FakeFunc(lambda *_a: 0)
            self.GetNamedSecurityInfoW = FakeFunc(lambda *_a: 0)
            self.EqualSid = FakeFunc(lambda *_a: 0)
            self.IsValidAcl = FakeFunc(lambda *_a: 0)

    class FakeWinDll_2:
        advapi32 = FakeAdvapi_2()
        kernel32 = FakeKernel_2()

    monkeypatch.setattr(ctypes, "windll", FakeWinDll_2(), raising=False)
    res2 = _inspect_windows_security_info(test_file)
    assert res2["api_available"] is True
    assert res2["api_success"] is False

    # 3. Ownership mismatch and invalid DACL
    closed_3: list[Any] = []
    freed_3: list[Any] = []

    class FakeKernel_3:
        def __init__(self) -> None:
            self.GetCurrentProcess = FakeFunc(lambda: 1)

            def _close(h: Any) -> int:
                closed_3.append(h)
                return 1

            def _free(m: Any) -> int:
                freed_3.append(m)
                return 0

            self.CloseHandle = FakeFunc(_close)
            self.LocalFree = FakeFunc(_free)

    class FakeAdvapi_3:
        def __init__(self) -> None:
            self.OpenProcessToken = FakeFunc(self._opt)
            self.GetTokenInformation = FakeFunc(self._gti)
            self.GetNamedSecurityInfoW = FakeFunc(self._gnsi)
            self.EqualSid = FakeFunc(lambda *_a: 0)  # Ownership mismatch
            self.IsValidAcl = FakeFunc(lambda *_a: 0)  # Invalid ACL

        def _opt(self, _proc: Any, _query: Any, tok_ref: Any) -> int:
            tok_ref._obj.value = 1234
            return 1

        def _gti(self, _tok: Any, _itype: Any, buf: Any, _buflen: Any, lenref: Any) -> int:
            lenref._obj.value = 68
            if buf is not None:
                ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p)).contents.value = 5678
            return 1

        def _gnsi(self, *args: Any) -> int:
            p_owner = args[3]
            p_dacl = args[5]
            p_sd = args[7]
            p_owner._obj.value = 9999
            p_dacl._obj.value = 7777
            p_sd._obj.value = 8888
            return 0

    class FakeWinDll_3:
        advapi32 = FakeAdvapi_3()
        kernel32 = FakeKernel_3()

    monkeypatch.setattr(ctypes, "windll", FakeWinDll_3(), raising=False)
    res3 = _inspect_windows_security_info(test_file)
    assert res3["api_success"] is True
    assert res3["owner_matched"] is False
    assert res3["dacl_present"] is True
    assert res3["dacl_valid"] is False
    assert len(closed_3) == 1
    assert len(freed_3) == 1


def test_windows_privacy_sentinels_no_raw_path_or_content_leaks(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Exceptions, representations, and logs must never disclose Windows paths, content, or SIDs."""
    _require_native_windows()

    root = tmp_path / "C_Users_SecretUser_AppData_Local"
    root.mkdir()
    source_path = root / "29-09-2026.md"
    secret_text = _make_valid_markdown(meaning="windows_secret_meaning_token")
    _write_fixture_bytes(source_path, secret_text)

    source = _make_source_file()
    adapter = SourceFileAdapter(root, allowlist={source.id: source})

    with pytest.raises(SourceConflictError) as exc_info:
        adapter.replace_source_content(
            source.id,
            _make_valid_markdown(word="new"),
            expected_content_hash="0000000000000000000000000000000000000000000000000000000000000000",
        )

    err_str = str(exc_info.value)
    err_repr = repr(exc_info.value)
    err_args = " ".join(str(a) for a in exc_info.value.args)

    for rendered in (err_str, err_repr, err_args, caplog.text):
        assert "C_Users_SecretUser_AppData_Local" not in rendered
        assert "windows_secret_meaning_token" not in rendered
        assert "S-1-5-" not in rendered
