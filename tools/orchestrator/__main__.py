"""python -m tools.orchestrator: single-task pipelines or repository DAG scheduling."""

import argparse
import json
import re
from pathlib import Path

from tools.orchestrator.core import OrchestratorError, State
from tools.orchestrator.recovery import recovery_handoff
from tools.orchestrator.scheduler import Scheduler
from tools.orchestrator.workflow import Pipeline

HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "run",
            "status",
            "resume",
            "retry",
            "schedule",
            "recover-candidate",
            "import-candidate",
            "verify-candidate",
        ],
    )
    parser.add_argument("task", nargs="?")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--expected-source-digest")
    parser.add_argument("--source-worktree", type=Path)
    parser.add_argument("--provenance-manifest", type=Path)
    parser.add_argument("--expected-provenance-digest")
    parser.add_argument("--dry-run", action="store_true")
    integration = parser.add_mutually_exclusive_group()
    integration.add_argument("--integrate", action="store_true")
    integration.add_argument("--no-integrate", action="store_true")
    args = parser.parse_args()
    if args.command != "schedule" and args.task is None:
        parser.error(
            "task is required for run/status/resume/retry/verify-candidate/recover-candidate/import-candidate"
        )
    if args.command == "import-candidate":
        if (
            not args.run_id
            or not args.source_worktree
            or not args.expected_source_digest
            or not args.provenance_manifest
            or not args.expected_provenance_digest
        ):
            parser.error(
                "import-candidate requires --run-id, --source-worktree, --expected-source-digest, "
                "--provenance-manifest, and --expected-provenance-digest"
            )
        if not HEX_SHA256_RE.fullmatch(args.expected_source_digest):
            parser.error("--expected-source-digest must be a 64-character lowercase hex string")
        if not HEX_SHA256_RE.fullmatch(args.expected_provenance_digest):
            parser.error("--expected-provenance-digest must be a 64-character lowercase hex string")
    else:
        if args.source_worktree is not None:
            parser.error("--source-worktree is supported only for import-candidate")
        if args.provenance_manifest is not None:
            parser.error("--provenance-manifest is supported only for import-candidate")
        if args.expected_provenance_digest is not None:
            parser.error("--expected-provenance-digest is supported only for import-candidate")

    if args.command == "recover-candidate":
        if not args.run_id or not args.expected_source_digest:
            parser.error("recover-candidate requires --run-id and --expected-source-digest")
        if not HEX_SHA256_RE.fullmatch(args.expected_source_digest):
            parser.error("--expected-source-digest must be a 64-character lowercase hex string")
    elif args.command != "import-candidate" and args.expected_source_digest is not None:
        parser.error(
            "--expected-source-digest is supported only for recover-candidate and import-candidate"
        )

    try:
        pipeline = Pipeline.load(Path.cwd(), args.config)
        if args.integrate:
            pipeline.config.integrate = True
        if args.no_integrate:
            pipeline.config.integrate = False
        if args.command == "schedule":
            if args.task is not None or args.run_id is not None:
                raise OrchestratorError("Schedule accepts neither a task nor --run-id")
            report = Scheduler(pipeline).run(dry_run=args.dry_run)
            print(json.dumps(report.model_dump(mode="json"), indent=2))
            return 2 if not args.dry_run and report.graph.blocked else 0
        if args.dry_run and args.command != "run":
            raise OrchestratorError("Dry run is supported only for run")
        if args.command == "run":
            if args.run_id:
                raise OrchestratorError(
                    "Run IDs are generated; use --run-id for status/resume/retry"
                )
            state = pipeline.start(args.task, dry_run=args.dry_run, defer_verification=True)
        elif args.command == "resume":
            selected = pipeline.status(args.task, args.run_id)
            if "recovery_origin" in selected.artifacts:
                control_plane = Path(__file__).resolve().parents[2]
                candidate_root = Path(selected.worktree_path).resolve()
                if control_plane == candidate_root or Path.cwd().resolve() == candidate_root:
                    handoff = recovery_handoff(
                        selected, args.config, integrate=pipeline.config.integrate
                    )
                    raise OrchestratorError(
                        "Recovered candidate resume requires trusted control-plane execution, "
                        f"not candidate modules. Run: {handoff.next_step}"
                    )
            elif "candidate_import_origin" in selected.artifacts:
                control_plane = Path(__file__).resolve().parents[2]
                candidate_root = Path(selected.worktree_path).resolve()
                if control_plane == candidate_root or Path.cwd().resolve() == candidate_root:
                    handoff = recovery_handoff(
                        selected, args.config, integrate=pipeline.config.integrate
                    )
                    raise OrchestratorError(
                        "Imported candidate resume requires trusted control-plane execution, "
                        f"not candidate modules. Run: {handoff.next_step}"
                    )
            state = pipeline.resume(args.task, args.run_id, defer_verification=True)
        elif args.command == "verify-candidate":
            if not args.run_id:
                raise OrchestratorError("verify-candidate requires --run-id")
            selected = pipeline.status(args.task, args.run_id)
            if selected.state != State.IMPLEMENTED:
                raise OrchestratorError("verify-candidate requires an IMPLEMENTED candidate")
            if args.integrate:
                raise OrchestratorError("verify-candidate cannot integrate into main")
            pipeline.config.integrate = False
            state = pipeline.resume(
                args.task, args.run_id, defer_verification=False, stop_after_audit=True
            )
        elif args.command == "recover-candidate":
            assert args.expected_source_digest is not None
            state = pipeline.recover_candidate(args.task, args.run_id, args.expected_source_digest)
        elif args.command == "import-candidate":
            assert args.run_id is not None
            assert args.source_worktree is not None
            assert args.expected_source_digest is not None
            assert args.provenance_manifest is not None
            assert args.expected_provenance_digest is not None
            state = pipeline.import_candidate(
                args.task,
                args.run_id,
                source_worktree=args.source_worktree,
                expected_source_digest=args.expected_source_digest,
                provenance_manifest=args.provenance_manifest,
                expected_provenance_digest=args.expected_provenance_digest,
            )
        elif args.command == "retry":
            state = pipeline.retry(args.task, args.run_id, defer_verification=True)
        else:
            state = pipeline.status(args.task, args.run_id)
        payload = state.model_dump(mode="json")
        if args.command == "recover-candidate" and state.state == State.IMPLEMENTED:
            payload["recovery_handoff"] = recovery_handoff(
                state, args.config, integrate=pipeline.config.integrate
            ).model_dump(mode="json")
        elif args.command == "import-candidate" and state.state == State.AUDIT_PASS:
            payload["candidate_import_handoff"] = recovery_handoff(
                state, args.config, integrate=pipeline.config.integrate
            ).model_dump(mode="json")
        print(json.dumps(payload, indent=2))
        return 2 if state.state in {State.BLOCKED, State.FAILED} else 0
    except (OrchestratorError, OSError, ValueError) as error:
        detail = str(error) if isinstance(error, OrchestratorError) else "inspect configuration/run"
        print(f"ERROR {type(error).__name__}: {detail}")
        return 2
    except KeyboardInterrupt:
        print("WARNING Interrupted; resume will inspect state before any work")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
