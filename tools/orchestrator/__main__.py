"""python -m tools.orchestrator: one task run per process, at most three processes."""

import argparse
import json
from pathlib import Path

from tools.orchestrator.core import OrchestratorError, State
from tools.orchestrator.workflow import Pipeline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "status", "resume", "retry"])
    parser.add_argument("task")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    integration = parser.add_mutually_exclusive_group()
    integration.add_argument("--integrate", action="store_true")
    integration.add_argument("--no-integrate", action="store_true")
    args = parser.parse_args()
    try:
        pipeline = Pipeline.load(Path.cwd(), args.config)
        if args.integrate:
            pipeline.config.integrate = True
        if args.no_integrate:
            pipeline.config.integrate = False
        if args.dry_run and args.command != "run":
            raise OrchestratorError("Dry run is supported only for run")
        if args.command == "run":
            if args.run_id:
                raise OrchestratorError(
                    "Run IDs are generated; use --run-id for status/resume/retry"
                )
            state = pipeline.start(args.task, dry_run=args.dry_run)
        elif args.command == "resume":
            state = pipeline.resume(args.task, args.run_id)
        elif args.command == "retry":
            state = pipeline.retry(args.task, args.run_id)
        else:
            state = pipeline.status(args.task, args.run_id)
        print(json.dumps(state.model_dump(mode="json"), indent=2))
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
