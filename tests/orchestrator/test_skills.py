import hashlib
from pathlib import Path

import pytest
from tools.orchestrator.core import OrchestratorError, TaskCard
from tools.orchestrator.skills import (
    SUPPORTED_SKILLS,
    build_manifest,
    check_skills,
    required_skills,
    skill_prompt,
)


def card(*, title: str, paths: list[str], criteria: list[str] | None = None) -> TaskCard:
    return TaskCard(
        task_id="T100",
        path="tasks/t100-test.md",
        title=title,
        objective=title,
        dependencies=[],
        allowed_paths=paths,
        acceptance_criteria=criteria or ["Required behavior"],
        required_verification=[["python", "-m", "pytest"]],
        content_digest="a" * 64,
        risk_level="high",
        context_text=(
            "Boilerplate docs/api-contract.md docs/security-review.md React SQLite migrations"
        ),
    )


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    pack = tmp_path / "pack" / "skills"
    for name in SUPPORTED_SKILLS:
        path = pack / name / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            f"---\nname: {name}\ndescription: Synthetic workflow\n---\nUse synthetic evidence.\n"
        )
    return pack


@pytest.mark.parametrize(
    "title,paths,criteria,expected,excluded",
    [
        (
            "Pure quiz scoring",
            ["backend/app/assessment/scoring.py"],
            ["Pure deterministic weakest rating"],
            {
                "incremental-implementation",
                "test-driven-development",
                "git-workflow-and-versioning",
                "documentation-and-adrs",
            },
            {
                "frontend-ui-engineering",
                "security-and-hardening",
                "doubt-driven-development",
                "api-and-interface-design",
            },
        ),
        (
            "Allowlisted Windows source adapter",
            ["backend/app/adapters/source_files.py"],
            ["Atomic replace; reparse escape fails closed"],
            {"security-and-hardening", "doubt-driven-development"},
            {"frontend-ui-engineering"},
        ),
        (
            "Consent UI",
            ["frontend/src/features/consent/Dialog.tsx"],
            None,
            {"frontend-ui-engineering", "security-and-hardening"},
            {"deprecation-and-migration"},
        ),
        (
            "Lookup API",
            ["backend/app/http/lookup.py", "frontend/src/shared/api/generated.ts"],
            None,
            {"api-and-interface-design", "security-and-hardening"},
            {"frontend-ui-engineering"},
        ),
        (
            "Source journal",
            ["backend/migrations/versions/0007_journal.py"],
            None,
            {"deprecation-and-migration", "doubt-driven-development"},
            {"frontend-ui-engineering"},
        ),
        (
            "Update guide",
            ["docs/orchestrator.md"],
            None,
            {"documentation-and-adrs", "git-workflow-and-versioning"},
            {"test-driven-development", "incremental-implementation"},
        ),
        (
            "Browser harness",
            ["frontend/tests/e2e/flow.spec.ts"],
            None,
            {"browser-testing-with-devtools"},
            {"deprecation-and-migration"},
        ),
        (
            "Search performance benchmark",
            ["scripts/benchmark_search.py"],
            None,
            {"performance-optimization"},
            {"frontend-ui-engineering"},
        ),
        (
            "Observability",
            ["backend/app/observability/logging.py"],
            None,
            {"observability-and-instrumentation"},
            {"deprecation-and-migration"},
        ),
        (
            "CI pipeline",
            [".github/workflows/checks.yml"],
            None,
            {"ci-cd-and-automation"},
            {"frontend-ui-engineering"},
        ),
    ],
)
def test_skill_selection_follows_task_not_boilerplate(
    title: str,
    paths: list[str],
    criteria: list[str] | None,
    expected: set[str],
    excluded: set[str],
) -> None:
    selected = required_skills(card(title=title, paths=paths, criteria=criteria), "worker")
    assert expected.issubset(selected)
    assert not excluded.intersection(selected)
    assert "using-agent-skills" not in selected
    assert len(selected) < len(SUPPORTED_SKILLS)
    assert all(selected.values())


def test_fix_and_review_have_phase_specific_skills() -> None:
    task = card(title="Pure scoring", paths=["backend/scoring.py"])
    assert "debugging-and-error-recovery" not in required_skills(task, "worker")
    assert "debugging-and-error-recovery" in required_skills(task, "fix")
    assert "code-review-and-quality" in required_skills(task, "auditor")


def test_manifest_pins_real_paths_hashes_and_reasons(pack: Path, tmp_path: Path) -> None:
    task = card(title="Lookup API", paths=["backend/app/http/lookup.py"])
    manifest = build_manifest(task, tmp_path, str(pack.parent))
    assert manifest.task_id == task.task_id
    assert manifest.task_digest == task.content_digest
    for entry in manifest.worker:
        assert Path(entry.path).is_file()
        assert entry.digest == hashlib.sha256(Path(entry.path).read_bytes()).hexdigest()
        assert entry.reason
    block = skill_prompt(manifest, "worker")
    assert "REQUIRED AGENT SKILLS" in block
    assert "Read" in block and "SKILL.md" in block
    assert "Do not commit" in block
    assert "mention is not proof" in skill_prompt(manifest, "auditor")


def test_configured_root_overrides_environment(
    pack: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENT_SKILLS_ROOT", str(tmp_path / "absent"))
    assert build_manifest(card(title="Code", paths=["feature.py"]), tmp_path, str(pack)).worker
    with pytest.raises(OrchestratorError, match="SETUP_FAILED"):
        build_manifest(card(title="Code", paths=["feature.py"]), tmp_path, str(tmp_path / "bad"))


def test_environment_root_and_native_agy_discovery(
    pack: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = card(title="Code", paths=["feature.py"])
    monkeypatch.setenv("AGENT_SKILLS_ROOT", str(pack))
    assert build_manifest(task, tmp_path).worker
    monkeypatch.delenv("AGENT_SKILLS_ROOT")
    native = tmp_path / ".gemini/config/plugins/agent-skills"
    native.mkdir(parents=True)
    (native / "skills").symlink_to(pack, target_is_directory=True)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert build_manifest(task, tmp_path).worker


@pytest.mark.parametrize("damage", ["deleted", "changed", "malformed", "oversized"])
def test_invalid_or_changed_skill_never_counts_as_available(
    pack: Path, tmp_path: Path, damage: str
) -> None:
    task = card(title="Code", paths=["feature.py"])
    manifest = build_manifest(task, tmp_path, str(pack))
    path = pack / "test-driven-development/SKILL.md"
    if damage == "deleted":
        path.unlink()
    elif damage == "changed":
        path.write_text(path.read_text() + "Changed workflow")
    elif damage == "malformed":
        path.write_text("Not a skill")
    else:
        path.write_text("x" * 140000)
    with pytest.raises(OrchestratorError, match="SETUP_FAILED"):
        check_skills(manifest)
    if damage in {"malformed", "oversized", "deleted"}:
        with pytest.raises(OrchestratorError, match="SETUP_FAILED"):
            build_manifest(task, tmp_path, str(pack))
