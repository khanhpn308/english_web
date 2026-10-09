"""Synthetic host-only T090 edit-interface tests; no provider security claims."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from tools.orchestrator.core import Config, OrchestratorError, Role
from tools.orchestrator.worker_sandbox import (
    HostEditRejected,
    LoopbackChatTransport,
    ProposedTextEdit,
    apply_host_text_edit,
    run_host_mediated_worker,
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
        apply_host_text_edit(root, {"src/ok.py"}, ProposedTextEdit(path, sha(original), "changed"))
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
        apply_host_text_edit(root, {"src/ok.py"}, ProposedTextEdit("src/ok.py", "BAD", "changed"))
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
        apply_host_text_edit(root, {"src/ok.py"}, ProposedTextEdit("src/ok.py", None, "changed"))
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


class FakeToolFreeTransport:
    """Synthetic text-only implementation; NOT a live vendor attestation."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.prompt = ""

    def complete(self, prompt: str, *, model: str, timeout: int | None) -> str:
        assert model == "gemini-3.8-flash-high"
        assert timeout is None
        self.prompt = prompt
        return json.dumps(self.response)


def proposal(edits: list[dict[str, object]], *, status: str = "IMPLEMENTED") -> dict[str, Any]:
    return {
        "status": status,
        "summary": "Synthetic model result",
        "known_issues": [],
        "edits": edits,
    }


def test_host_worker_completes_without_any_agent_command(tmp_path: Path) -> None:
    root, original = fixture(tmp_path)
    fake = FakeToolFreeTransport(
        proposal(
            [
                {
                    "path": "src/ok.py",
                    "expected_sha256": sha(original),
                    "replacement": "updated\n",
                }
            ]
        )
    )
    result = run_host_mediated_worker(
        root,
        {"src/ok.py"},
        "Strict synthetic task",
        model="gemini-3.8-flash-high",
        transport=fake,
    )
    assert result.status == "IMPLEMENTED"
    assert result.commands_run == []
    assert result.changed_files == ["src/ok.py"]
    assert (root / "src/ok.py").read_text() == "updated\n"
    assert "original" in fake.prompt
    assert "private.txt" not in fake.prompt


@pytest.mark.parametrize(
    "invalid",
    [
        {"commands_run": [["git", "status"]]},
        {"tool_calls": [{"function": {"name": "shell"}}]},
        {"edits": []},
    ],
)
def test_host_rejects_tool_instructions_extra_fields_or_empty_edits(
    tmp_path: Path, invalid: dict[str, Any]
) -> None:
    root, original = fixture(tmp_path)
    base = proposal(
        [{"path": "src/ok.py", "expected_sha256": sha(original), "replacement": "updated"}]
    )
    base.update(invalid)
    with pytest.raises(HostEditRejected):
        run_host_mediated_worker(
            root,
            {"src/ok.py"},
            "task",
            model="gemini-3.8-flash-high",
            transport=FakeToolFreeTransport(base),
        )
    assert (root / "src/ok.py").read_bytes() == original


@pytest.mark.parametrize(
    "edits",
    [
        [{"path": "private.txt", "expected_sha256": sha(b"protected"), "replacement": "bad"}],
        [{"path": "../private.txt", "expected_sha256": sha(b"protected"), "replacement": "bad"}],
        [{"path": "src/ok.py", "expected_sha256": sha(b"stale"), "replacement": "bad"}],
        [
            {"path": "src/ok.py", "expected_sha256": sha(b"original\n"), "replacement": "a"},
            {"path": "src/ok.py", "expected_sha256": sha(b"original\n"), "replacement": "b"},
        ],
    ],
)
def test_host_rejects_out_of_scope_stale_duplicate_path_without_write(
    tmp_path: Path, edits: list[dict[str, object]]
) -> None:
    root, original = fixture(tmp_path)
    with pytest.raises(HostEditRejected):
        run_host_mediated_worker(
            root,
            {"src/ok.py"},
            "task",
            model="gemini-3.8-flash-high",
            transport=FakeToolFreeTransport(proposal(edits)),
        )
    assert (root / "src/ok.py").read_bytes() == original
    assert (root / "private.txt").read_text() == "protected"


def test_host_preflights_all_edits_before_any_write(tmp_path: Path) -> None:
    root, original = fixture(tmp_path)
    fake = FakeToolFreeTransport(
        proposal(
            [
                {"path": "src/ok.py", "expected_sha256": sha(original), "replacement": "changed"},
                {
                    "path": "src/next.py",
                    "expected_sha256": None,
                    "replacement": "x" * (256 * 1024 + 1),
                },
            ]
        )
    )
    with pytest.raises(HostEditRejected, match="size/text"):
        run_host_mediated_worker(
            root,
            {"src/ok.py", "src/next.py"},
            "task",
            model="gemini-3.8-flash-high",
            transport=fake,
        )
    assert (root / "src/ok.py").read_bytes() == original
    assert not (root / "src/next.py").exists()


def test_blocked_model_response_never_edits(tmp_path: Path) -> None:
    root, original = fixture(tmp_path)
    out = run_host_mediated_worker(
        root,
        {"src/ok.py"},
        "task",
        model="gemini-3.8-flash-high",
        transport=FakeToolFreeTransport(proposal([], status="BLOCKED")),
    )
    assert out.status == "BLOCKED"
    assert out.changed_files == []
    assert out.commands_run == []
    assert (root / "src/ok.py").read_bytes() == original


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8045/v1/chat/completions",
        "http://localhost:8045/v1/chat/completions",
        "http://192.168.1.2:8045/v1/chat/completions",
        "http://127.0.0.1:8045/unsafe",
        "http://user:password@127.0.0.1:8045/v1/chat/completions",
        "http://127.0.0.1:8045/v1/chat/completions?bypass=1",
    ],
)
def test_host_transport_rejects_unsafe_endpoints(url: str) -> None:
    with pytest.raises(HostEditRejected, match="loopback"):
        LoopbackChatTransport(url, api_key_env="SAFE_TEST_KEY")


def test_transport_requires_credentials_before_any_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SAFE_TEST_KEY", raising=False)
    client = LoopbackChatTransport(
        "http://127.0.0.1:8045/v1/chat/completions",
        api_key_env="SAFE_TEST_KEY",
    )
    with pytest.raises(HostEditRejected, match="credential"):
        client.complete("test", model="gemini-3.8-flash-high", timeout=1)


def test_transport_issues_explicit_tool_free_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAFE_TEST_KEY", "synthetic-test-value")
    client = LoopbackChatTransport(
        "http://127.0.0.1:8045/v1/chat/completions",
        api_key_env="SAFE_TEST_KEY",
    )
    expected = '{"status":"BLOCKED","summary":"No changes","known_issues":[],"edits":[]}'
    envelope = {
        "choices": [
            {
                "message": {"role": "assistant", "content": expected},
                "finish_reason": "stop",
            }
        ]
    }

    class FakeHTTPResponse:
        status = 200

        def __enter__(self) -> "FakeHTTPResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, amount: int) -> bytes:
            assert amount == 4 * 1024 * 1024 + 1
            return json.dumps(envelope).encode()

    class FakeOpener:
        def open(self, request: Any, timeout: int) -> FakeHTTPResponse:
            assert timeout == 5
            payload = json.loads(request.data)
            assert payload["tools"] == []
            assert payload["tool_choice"] == "none"
            assert payload["stream"] is False
            assert payload["model"] == "gemini-3.8-flash-high"
            assert payload["messages"][1]["content"] == "Synthetic request"
            return FakeHTTPResponse()

    monkeypatch.setattr(client, "_opener", FakeOpener())
    assert (
        client.complete("Synthetic request", model="gemini-3.8-flash-high", timeout=5) == expected
    )


def test_transport_rejects_any_model_tool_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAFE_TEST_KEY", "synthetic-test-value")
    client = LoopbackChatTransport(
        "http://127.0.0.1:8045/v1/chat/completions",
        api_key_env="SAFE_TEST_KEY",
    )

    class BadHTTPResponse:
        status = 200

        def __enter__(self) -> "BadHTTPResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, amount: int) -> bytes:
            assert amount == 4 * 1024 * 1024 + 1
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "{}",
                                "tool_calls": [{"id": "forbidden"}],
                            },
                            "finish_reason": "stop",
                        }
                    ]
                }
            ).encode()

    class FakeOpener:
        def open(self, request: Any, timeout: int) -> BadHTTPResponse:
            assert request.get_method() == "POST"
            assert timeout == 5
            return BadHTTPResponse()

    monkeypatch.setattr(client, "_opener", FakeOpener())
    with pytest.raises(HostEditRejected, match="tool-free"):
        client.complete("task", model="gemini-3.8-flash-high", timeout=5)


def _host_roles() -> dict[str, Role]:
    roles = {
        name: Role(provider="codex", executable="synthetic-codex")
        for name in ("prompt_engineer", "worker", "auditor", "integrator")
    }
    roles["worker"] = Role(
        provider="agy",
        executable="agy",
        model="gemini-3.8-flash-high",
        allow_process=False,
        worker_access="workspace-write",
        worker_backend="host-http-edit",
        host_edit_endpoint="http://127.0.0.1:8045/v1/chat/completions",
        host_edit_api_key_env="SAFE_TEST_KEY",
    )
    return roles


def test_host_edit_backend_must_be_explicitly_and_safely_configured() -> None:
    roles = _host_roles()
    Config(roles=roles, verification=[["python", "-m", "pytest"]]).validate_roles()
    for changes in (
        {"allow_process": True},
        {"worker_access": "full-access"},
        {"host_edit_endpoint": "http://192.168.1.2:8045/v1/chat/completions"},
        {"host_edit_api_key_env": None},
        {"model": None},
    ):
        bad_roles = {**roles, "worker": roles["worker"].model_copy(update=changes)}
        with pytest.raises((OrchestratorError, HostEditRejected)):
            Config(roles=bad_roles, verification=[["python", "-m", "pytest"]]).validate_roles()


def test_host_edit_transport_rejected_for_nonworker_roles() -> None:
    roles = _host_roles()
    roles["auditor"] = roles["worker"]
    with pytest.raises(OrchestratorError, match="belongs to Worker"):
        Config(roles=roles, verification=[["python", "-m", "pytest"]]).validate_roles()


def test_t090_semantic_roles_require_explicit_tool_free_endpoint() -> None:
    roles = _host_roles()
    analyst = Role(
        provider="agy",
        executable="not-used-for-semantic-http",
        model="gemini-3.8-flash-high",
        analysis_backend="host-http-text",
        host_text_endpoint="http://127.0.0.1:8045/v1/chat/completions",
        host_text_api_key_env="T090_TEST_ONLY_KEY",
    )
    for name in ("prompt_engineer", "auditor", "integrator"):
        roles[name] = analyst
    Config(roles=roles, verification=[["python", "-m", "pytest"]]).validate_roles()

    for changes in (
        {"model": None},
        {"host_text_endpoint": None},
        {"host_text_api_key_env": None},
        {"host_text_endpoint": "http://192.168.1.2:8045/v1/chat/completions"},
        {"allow_process": True},
        {"worker_access": "full-access"},
    ):
        failed = dict(roles)
        failed["auditor"] = analyst.model_copy(update=changes)
        with pytest.raises((OrchestratorError, HostEditRejected)):
            Config(roles=failed, verification=[["python", "-m", "pytest"]]).validate_roles()


def test_t090_rejects_tool_free_analyst_backend_on_worker() -> None:
    roles = _host_roles()
    roles["worker"] = roles["worker"].model_copy(
        update={
            "analysis_backend": "host-http-text",
            "host_text_endpoint": "http://127.0.0.1:8045/v1/chat/completions",
            "host_text_api_key_env": "T090_TEST_ONLY_KEY",
        }
    )
    with pytest.raises(OrchestratorError, match="belongs to read-only"):
        Config(roles=roles, verification=[["python", "-m", "pytest"]]).validate_roles()


def test_t090_rejects_hidden_host_text_options_in_cli_role() -> None:
    roles = _host_roles()
    roles["auditor"] = roles["auditor"].model_copy(
        update={"host_text_endpoint": "http://127.0.0.1:8045/v1/chat/completions"}
    )
    with pytest.raises(OrchestratorError, match="requires host-http-text"):
        Config(roles=roles, verification=[["python", "-m", "pytest"]]).validate_roles()


def test_t090_semantic_transport_has_role_schema_not_worker_edit_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SAFE_TEST_KEY", "synthetic-only")
    client = LoopbackChatTransport(
        "http://127.0.0.1:8045/v1/chat/completions",
        api_key_env="SAFE_TEST_KEY",
        response_contract="semantic-json",
    )

    class Response:
        status = 200

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, amount: int) -> bytes:
            assert amount == 4 * 1024 * 1024 + 1
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": '{"fix_prompt":"KEEP_SAFE"}',
                            },
                            "finish_reason": "stop",
                        }
                    ]
                }
            ).encode()

    class Opener:
        def open(self, request: Any, timeout: int) -> Response:
            assert timeout == 5
            payload = json.loads(request.data)
            assert payload["tools"] == []
            assert payload["tool_choice"] == "none"
            assert "WorkerEditResponse" not in payload["messages"][0]["content"]
            assert "role output schema" in payload["messages"][0]["content"]
            assert "Fix" in payload["messages"][1]["content"]
            return Response()

    monkeypatch.setattr(client, "_opener", Opener())
    assert (
        client.complete("Fix output schema", model="gemini-3.8-flash-high", timeout=5)
        == '{"fix_prompt":"KEEP_SAFE"}'
    )
