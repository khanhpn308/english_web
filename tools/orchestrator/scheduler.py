"""Repository DAG admission above the existing, authoritative per-task Pipeline."""

import multiprocessing
import re
from concurrent.futures import FIRST_COMPLETED, Executor, Future, ProcessPoolExecutor, wait
from graphlib import CycleError, TopologicalSorter
from pathlib import Path, PurePosixPath
from time import sleep

from pydantic import Field
from tools.orchestrator.core import (
    TASK_PATTERN,
    Model,
    OrchestratorError,
    State,
    TaskId,
    dependency_ids,
    task_card,
)
from tools.orchestrator.runtime import Git, LockBusy, lock
from tools.orchestrator.workflow import Pipeline


class Metadata(Model):
    task_id: TaskId
    path: str
    status: str
    dependencies: list[TaskId]
    title: str


class Graph(Model):
    revision: str | None = None
    tasks: dict[str, Metadata]
    topological_order: list[TaskId]
    done: list[TaskId]
    ready: list[TaskId]
    blocked: dict[str, list[str]]


class Outcome(Model):
    task_id: TaskId
    state: State
    run_id: str | None = None
    reason: str | None = None


class Report(Model):
    dry_run: bool
    graph: Graph
    outcomes: dict[str, Outcome] = Field(default_factory=dict)


def metadata(path: str, text: str) -> Metadata:
    """Read graph facts only; executable contracts and DONE evidence belong to core."""
    heading = re.search(r"^# (" + TASK_PATTERN + r")(?=\s|:|$)", text, re.M)
    identifier = re.search(r"^\*\*Task ID:\*\*\s*`(" + TASK_PATTERN + r")`", text, re.M)
    filename = re.fullmatch(r"tasks/(t[0-9]{3})-[^/]+\.md", path)
    status = re.search(r"^\*\*Status:\*\*\s*`([A-Z][A-Z0-9_]*)`", text, re.M)
    title = re.search(r"^\*\*Title:\*\*\s*([^\n]+)", text, re.M)
    if (
        heading is None
        or filename is None
        or status is None
        or title is None
        or filename[1].upper() != heading[1]
        or (identifier is not None and identifier[1] != heading[1])
        or ("**Task ID:**" in text and identifier is None)
    ):
        raise OrchestratorError(f"Invalid task metadata: {path}")
    dependencies = dependency_ids(text)
    return Metadata(
        task_id=heading[1],
        path=path,
        status=status[1],
        title=title[1].strip(),
        dependencies=dependencies,
    )


def discover(repository: Path, revision: str | None = None) -> dict[str, Metadata]:
    """Discover even blocked cards without task_card() dependency enforcement.

    Production scans a single immutable canonical Git revision. The filesystem
    reader is also useful for synthetic graph fixtures; it never creates files.
    """
    cards: list[Metadata] = []
    if revision is None:
        root = repository / "tasks"
        if root.is_symlink():
            raise OrchestratorError("Task directory must not be a symlink")
        for path in sorted(root.glob("t[0-9]*.md")):
            if not path.is_file() or path.is_symlink():
                raise OrchestratorError("Expected a regular task card")
            cards.append(metadata(path.relative_to(repository).as_posix(), path.read_text("utf-8")))
    else:
        git = Git(repository)
        entries = git.run("ls-tree", "-r", "-z", revision, "--", "tasks").split("\0")
        for entry in sorted(filter(None, entries)):
            descriptor, relative = entry.split("\t", 1)
            if not PurePosixPath(relative).match("tasks/t[0-9]*.md"):
                continue
            if descriptor.split()[0] not in {"100644", "100755"}:
                raise OrchestratorError(f"Expected a regular task card: {relative}")
            text = git.run("show", f"{revision}:{relative}", preserve_newlines=True)
            cards.append(metadata(relative, text))
    if not cards:
        raise OrchestratorError("No repository task cards found")
    counts: dict[str, int] = {}
    for card in cards:
        counts[card.task_id] = counts.get(card.task_id, 0) + 1
    duplicates = sorted(task for task, count in counts.items() if count > 1)
    if duplicates:
        raise OrchestratorError("Duplicate task IDs: " + ", ".join(duplicates))
    return {card.task_id: card for card in sorted(cards, key=lambda card: card.task_id)}


def resolve(
    tasks: dict[str, Metadata],
    outcomes: dict[str, Outcome] | None = None,
    *,
    revision: str | None = None,
) -> Graph:
    """Validate every edge, including DONE nodes, before admitting any work."""
    tasks = dict(sorted(tasks.items()))
    for task, card in tasks.items():
        for dep in card.dependencies:
            if dep == task:
                raise OrchestratorError(f"Self dependency: {task}")
            if dep not in tasks:
                raise OrchestratorError(f"Missing dependency: {task} -> {dep}")
    try:
        sorter = TopologicalSorter({t: c.dependencies for t, c in tasks.items()})
        order = list(sorter.static_order())
    except CycleError as error:
        raise OrchestratorError("Dependency cycle: " + " -> ".join(error.args[1])) from error
    outcomes = outcomes or {}

    def status(task: str) -> str:
        if tasks[task].status == "DONE":
            return "DONE"
        if task in outcomes:
            state = outcomes[task].state.value
            return state + " (canonical card is not DONE)" if state == "DONE" else state
        return tasks[task].status

    done: list[str] = []
    ready: list[str] = []
    blocked: dict[str, list[str]] = {}
    for task, card in tasks.items():
        if card.status == "DONE":
            done.append(task)
            continue
        reasons = [f"{dep}: {status(dep)}" for dep in card.dependencies if status(dep) != "DONE"]
        if task in outcomes:
            reasons.insert(0, f"Run ended at {status(task)}; inspect run before further work")
        elif "BLOCKED" in card.status or "FAILED" in card.status:
            reasons.insert(0, f"Task status: {card.status}")
        if reasons:
            blocked[task] = reasons
        else:
            ready.append(task)
    return Graph(
        revision=revision,
        tasks=tasks,
        topological_order=order,
        done=done,
        ready=ready,
        blocked=blocked,
    )


def dispatch(pipeline: Pipeline, task: str) -> Outcome:
    """Use authoritative preflight and Pipeline; never reproduce its run semantics."""
    try:
        task_card(pipeline.repository, task)
        state = pipeline.start(task)
        return Outcome(
            task_id=task, state=state.state, run_id=state.run_id, reason=state.last_error
        )
    except LockBusy:
        # Admission/task lock contention is not a failed implementation attempt.
        raise
    except (OrchestratorError, OSError, ValueError) as error:
        return Outcome(
            task_id=task,
            state=State.FAILED,
            reason=str(error) if isinstance(error, OrchestratorError) else type(error).__name__,
        )


class Scheduler:
    def __init__(self, pipeline: Pipeline) -> None:
        self.pipeline = pipeline
        self._revision: str | None = None
        self._tasks: dict[str, Metadata] = {}

    def scan(self, outcomes: dict[str, Outcome] | None = None) -> Graph:
        revision = self.pipeline.git.sha(f"refs/heads/{self.pipeline.config.base_branch}")
        if revision != self._revision:
            self._tasks = discover(self.pipeline.repository, revision)
            self._revision = revision
        return resolve(self._tasks, outcomes, revision=revision)

    def run(self, *, dry_run: bool = False, executor: Executor | None = None) -> Report:
        graph = self.scan()
        if dry_run:
            return Report(dry_run=True, graph=graph)
        # One repository-wide scheduler, while ordinary Level 1 commands keep
        # their existing per-task locks. Dry-run does not even create lock files.
        with lock(self.pipeline.locks / "scheduler.lock"):
            if executor is not None:
                return self.drive(executor)
            # Separate processes preserve runtime's process-local lock inheritance
            # and synchronous providers. The pool is a dispatch bound, not a lock.
            with ProcessPoolExecutor(
                max_workers=3, mp_context=multiprocessing.get_context("spawn")
            ) as pool:
                return self.drive(pool)

    def drive(self, executor: Executor) -> Report:
        outcomes: dict[str, Outcome] = {}
        live: dict[Future[Outcome], str] = {}
        deferred: set[str] = set()
        while True:
            graph = self.scan(outcomes)
            active = set(live.values())
            for task in graph.ready:
                if len(live) >= 3:
                    break
                if task not in active and task not in deferred:
                    live[executor.submit(dispatch, self.pipeline, task)] = task
                    active.add(task)
            if not live:
                if graph.ready:
                    # Let other READY nodes pass busy task locks before polling
                    # the deferred nodes again. OS locks remain authoritative.
                    sleep(0.1)
                    deferred.clear()
                    continue
                return Report(dry_run=False, graph=graph, outcomes=outcomes)
            completed, _pending = wait(
                live, timeout=0.5 if deferred else None, return_when=FIRST_COMPLETED
            )
            if not completed:
                # External admission owners can finish while our tasks are still
                # running; retry contention without waiting for those tasks.
                deferred.clear()
                continue
            for future in sorted(completed, key=lambda future: live[future]):
                task = live.pop(future)
                try:
                    outcomes[task] = future.result()
                except LockBusy:
                    deferred.add(task)
                except Exception as error:
                    # Unexpected worker failure is isolated and never logs input.
                    outcomes[task] = Outcome(
                        task_id=task, state=State.FAILED, reason=type(error).__name__
                    )
            # Always re-read canonical Git, including after a reported DONE. A
            # run/worktree result alone cannot satisfy any dependency edge.
