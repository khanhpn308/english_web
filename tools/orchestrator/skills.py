"""Task-scoped skill references; no plugin install or LLM-controlled routing."""

import os
import re
from pathlib import Path
from typing import Literal

from pydantic import Field
from tools.orchestrator.core import (
    Model,
    Nonempty,
    OrchestratorError,
    Sha,
    TaskCard,
    TaskId,
    digest,
)

Phase = Literal["worker", "fix", "auditor"]
SUPPORTED_SKILLS = (
    "incremental-implementation",
    "test-driven-development",
    "git-workflow-and-versioning",
    "documentation-and-adrs",
    "api-and-interface-design",
    "frontend-ui-engineering",
    "security-and-hardening",
    "doubt-driven-development",
    "browser-testing-with-devtools",
    "ci-cd-and-automation",
    "performance-optimization",
    "observability-and-instrumentation",
    "deprecation-and-migration",
    "source-driven-development",
    "debugging-and-error-recovery",
    "code-review-and-quality",
)
SKILL_LIMIT = 128 * 1024


class SkillReference(Model):
    name: Nonempty
    path: Nonempty
    digest: Sha
    reason: Nonempty


class SkillManifest(Model):
    schema_version: Literal[1] = 1
    task_id: TaskId
    task_digest: Sha
    worker: list[SkillReference] = Field(min_length=1)
    fix: list[SkillReference] = Field(min_length=1)
    auditor: list[SkillReference] = Field(min_length=1)


def required_skills(card: TaskCard, phase: Phase) -> dict[str, str]:
    # Only task-owned paths and actual requirements classify work. Dependency/docs
    # boilerplate mentions UI/API/security in nearly every card and is not a trigger.
    paths = [p.lower() for p in card.allowed_paths if not p.startswith(("tasks/", "docs/"))]
    semantics = (card.title + " " + card.objective).lower()
    requirements = semantics + " " + " ".join(card.acceptance_criteria).lower()
    coding = any(Path(p).suffix not in {".md", ".toml", ".yaml", ".yml", ".json"} for p in paths)
    selected = {
        "git-workflow-and-versioning": "Preserve the task branch, scoped diff and host-owned Git."
    }
    if coding:
        selected["incremental-implementation"] = (
            "Implement the owned change in small verifiable increments."
        )
        if not re.search(r"\b(formatting|lint-only|mechanical)\b", semantics):
            selected["test-driven-development"] = (
                "Establish baseline and RED/GREEN behavior with repository tests."
            )
    if any(
        p.endswith(".tsx") or (p.startswith("frontend/src/") and "/shared/api/" not in p)
        for p in paths
    ):
        selected["frontend-ui-engineering"] = "Task owns frontend components or state wiring."
    if any("/e2e/" in p or "playwright" in p for p in paths) or re.search(
        r"\b(browser|accessibility|a11y)\b", semantics
    ):
        selected["browser-testing-with-devtools"] = (
            "Task requires browser runtime verification; use task-owned harness."
        )
    if any(p.startswith("backend/app/http/") or "/shared/api/" in p for p in paths) or re.search(
        r"\b(api|endpoint|http|openapi|dto|interface)\b", semantics
    ):
        selected["api-and-interface-design"] = (
            "Task changes an API/interface boundary and typed error semantics."
        )
    if any(
        p.startswith(("backend/app/http/", "backend/app/persistence/", "backend/app/adapters/"))
        for p in paths
    ) or re.search(
        r"\b(consent|admission|security|privacy|allowlist\w*|authentication|authorization|parser)\b",
        requirements,
    ):
        selected["security-and-hardening"] = (
            "Task crosses an input, filesystem, persistence or consent boundary."
        )
    if any(p.startswith("backend/migrations/") for p in paths):
        selected["deprecation-and-migration"] = (
            "Task owns a database migration; preserve lineage and existing data."
        )
    if (
        card.risk_level == "critical"
        or any(p.startswith("backend/migrations/") for p in paths)
        or re.search(
            r"\b(concurren\w*|race|cas|atomic|crash|durable|transaction\w*|revocation|journal\w*|reparse)\b",
            requirements,
        )
    ):
        selected["doubt-driven-development"] = (
            "Task has correctness-sensitive ordering, recovery or security invariants."
        )
    if any(p == "package.json" or p.startswith(".github/workflows/") for p in paths) or re.search(
        r"\b(ci|cd|pipeline)\b", semantics
    ):
        selected["ci-cd-and-automation"] = "Task owns build/verification automation."
    if re.search(r"\b(performance|benchmark\w*|profil\w*|latency|p95)\b", requirements):
        selected["performance-optimization"] = (
            "Task has measurable performance acceptance criteria."
        )
    if re.search(r"\b(observability|logging|telemetry|tracing|instrumentation)\b", semantics):
        selected["observability-and-instrumentation"] = (
            "Task implements diagnostic behavior and privacy-safe evidence."
        )
    if re.search(r"\b(cli|sdk|provider|bridge)\b", semantics):
        selected["source-driven-development"] = (
            "Task depends on actual external tool/library capabilities."
        )
    selected["documentation-and-adrs"] = (
        "Repository requires scoped task bookkeeping and changelog documentation."
    )
    if phase == "fix":
        selected["debugging-and-error-recovery"] = (
            "Reproduce and remediate concrete Auditor findings without scope expansion."
        )
    if phase == "auditor":
        selected = {
            k: v
            for k, v in selected.items()
            if k
            in {
                "security-and-hardening",
                "doubt-driven-development",
                "performance-optimization",
                "frontend-ui-engineering",
                "api-and-interface-design",
                "deprecation-and-migration",
            }
        }
        selected["code-review-and-quality"] = (
            "Independently inspect actual diff, acceptance coverage and executable evidence."
        )
    return selected


def skill_roots(repository: Path, configured: str | None) -> list[Path]:
    explicit = configured if configured is not None else os.environ.get("AGENT_SKILLS_ROOT")
    if explicit is not None:
        if not explicit.strip():
            raise OrchestratorError("SETUP_FAILED: empty agent skill root")
        root = Path(explicit).expanduser()
        candidates = [root if root.is_absolute() else repository / root]
    else:
        home = Path.home()
        candidates = [
            repository / ".agents/skills",
            repository / ".gemini/skills",
            home / ".gemini/config/plugins/agent-skills/skills",
            home / ".gemini/skills",
            home / ".agents/skills",
            home / ".codex/skills",
        ]
        candidates.extend(
            sorted(
                (home / ".codex/plugins/cache/agent-skills/agent-skills").glob("*/skills"),
                reverse=True,
            )
        )
    return [(p / "skills" if (p / "skills").is_dir() else p).resolve() for p in candidates]


def skill_bytes(path: Path, name: str) -> bytes:
    try:
        with path.open("rb") as stream:
            content = stream.read(SKILL_LIMIT + 1)
        if len(content) > SKILL_LIMIT:
            raise ValueError("oversized")
        text = content.decode("utf-8")
        if not text.startswith("---\n") or not re.search(
            r"(?m)^name:\s*[\"']?" + re.escape(name) + r"[\"']?\s*$", text
        ):
            raise ValueError("invalid skill name")
        return content
    except (OSError, UnicodeError, ValueError) as error:
        raise OrchestratorError(f"SETUP_FAILED: unavailable/invalid agent skill: {name}") from error


def build_manifest(
    card: TaskCard, repository: Path, configured: str | None = None
) -> SkillManifest:
    roots = skill_roots(repository, configured)
    phases: dict[Phase, list[SkillReference]] = {}
    for phase in ("worker", "fix", "auditor"):
        entries = []
        for name, reason in required_skills(card, phase).items():
            path = next(
                (p / name / "SKILL.md" for p in roots if (p / name / "SKILL.md").is_file()), None
            )
            if path is None:
                raise OrchestratorError(f"SETUP_FAILED: required agent skill missing: {name}")
            path = path.resolve()
            entries.append(
                SkillReference(
                    name=name, path=str(path), digest=digest(skill_bytes(path, name)), reason=reason
                )
            )
        phases[phase] = entries
    return SkillManifest(
        task_id=card.task_id,
        task_digest=card.content_digest,
        worker=phases["worker"],
        fix=phases["fix"],
        auditor=phases["auditor"],
    )


def check_skills(manifest: SkillManifest) -> None:
    for entry in (*manifest.worker, *manifest.fix, *manifest.auditor):
        if entry.name not in SUPPORTED_SKILLS or not Path(entry.path).is_absolute():
            raise OrchestratorError("SETUP_FAILED: invalid agent skill reference")
        if digest(skill_bytes(Path(entry.path), entry.name)) != entry.digest:
            raise OrchestratorError(
                f"SETUP_FAILED: agent skill changed since planning: {entry.name}"
            )


def skill_prompt(manifest: SkillManifest, phase: Phase) -> str:
    entries = getattr(manifest, phase)
    return (
        "\nREQUIRED AGENT SKILLS\n"
        "Read each listed SKILL.md before implementation/review and apply its relevant workflow.\n"
        "Load supporting references only when needed; do not preload the whole pack/meta-router.\n"
        + "\n".join(
            f"- {s.name}: Read {s.path} (SHA256 {s.digest}). Why: {s.reason}" for s in entries
        )
        + "\nUser instruction, task contract and repository rules override skill suggestions.\n"
        "Skills never expand allowed paths, acceptance criteria, verification "
        "or product requirements.\n"
        "Do not commit, merge, push, change state, install tools or alter CLI settings.\n"
        "Host owns Git.\n"
        "Do not demand routine approval or block for optional cross-model review.\n"
        "Use repository concurrency limits; never run real inference as a test.\n"
        "Record skills read and concrete application/evidence in existing "
        "JSON summary/evidence fields.\n"
        "A skill mention is not proof it was followed: audit tests, scope, "
        "checks and implementation.\n"
        "Return only the role JSON; do not add unsupported schema fields.\n"
    )
