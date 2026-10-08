"""Filesystem watcher adapter for Markdown vocabulary source files (T023).

Monitors a configured directory for Markdown source file changes, debounces rapid
bursts of events (coalescing storms), and invokes an injected callback.
Boundary rules: This adapter never imports application, HTTP, composition, or other adapters.
"""

from __future__ import annotations

import contextlib
import os
import stat
import threading
import time
from collections.abc import Callable
from pathlib import Path


class SourceWatcher:
    """Coalescing, debouncing filesystem watcher for Markdown sources."""

    def __init__(
        self,
        root_path: Path | str,
        on_change: Callable[[list[str]], None],
        *,
        on_error: Callable[[list[str], Exception], None] | None = None,
        debounce_seconds: float = 0.5,
        poll_interval: float = 0.1,
    ) -> None:
        self.root_path = Path(root_path).resolve()
        self.on_change = on_change
        self.on_error = on_error
        self.debounce_seconds = debounce_seconds
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_state: dict[str, tuple[int, int]] = {}  # rel_path -> (mtime_ns, size)
        self.last_error: Exception | None = None
        self.last_failed_batch: list[str] | None = None

    def _scan(self) -> dict[str, tuple[int, int]]:
        """Scan root directory for non-hidden .md files."""
        current: dict[str, tuple[int, int]] = {}
        if not self.root_path.exists() or not self.root_path.is_dir():
            return current

        for root, dirs, files in os.walk(self.root_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for file in files:
                if file.startswith(".") or not file.endswith(".md"):
                    continue
                full_path = Path(root) / file
                try:
                    st = os.stat(full_path, follow_symlinks=False)
                    if not stat.S_ISREG(st.st_mode):
                        continue
                    rel = full_path.relative_to(self.root_path).as_posix()
                    current[rel] = (st.st_mtime_ns, st.st_size)
                except OSError:
                    continue
        return current

    def poll_now(self) -> list[str]:
        """Synchronously check for changes and return changed relative paths."""
        with self._lock:
            current = self._scan()
            changed: list[str] = []
            for path, meta in current.items():
                if path not in self._last_state or self._last_state[path] != meta:
                    changed.append(path)
            for path in list(self._last_state.keys()):
                if path not in current:
                    changed.append(path)
            self._last_state = current
            return changed

    def _run(self) -> None:
        """Background monitoring loop with debouncing."""
        pending_changes: set[str] = set()
        last_change_time: float = 0.0

        while not self._stop_event.is_set():
            changes = self.poll_now()
            now = time.monotonic()
            if changes:
                pending_changes.update(changes)
                last_change_time = now

            if pending_changes and (now - last_change_time >= self.debounce_seconds):
                batch = sorted(pending_changes)
                pending_changes.clear()
                try:
                    self.on_change(batch)
                except Exception as exc:
                    self.last_error = exc
                    self.last_failed_batch = batch
                    if self.on_error is not None:
                        with contextlib.suppress(Exception):
                            self.on_error(batch, exc)

            self._stop_event.wait(timeout=self.poll_interval)

        # Flush any remaining changes on shutdown
        if pending_changes:
            batch = sorted(pending_changes)
            pending_changes.clear()
            try:
                self.on_change(batch)
            except Exception as exc:
                self.last_error = exc
                self.last_failed_batch = batch
                if self.on_error is not None:
                    with contextlib.suppress(Exception):
                        self.on_error(batch, exc)

    def capture_baseline(self) -> dict[str, tuple[int, int]]:
        """Establish baseline before startup sync so external edits during startup are detected."""
        with self._lock:
            self._last_state = self._scan()
            return dict(self._last_state)

    def start(self) -> None:
        """Start the background monitor thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            if not self._last_state:
                self._last_state = self._scan()
            self._thread = threading.Thread(target=self._run, daemon=True, name="source-watcher")
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop and join the background monitor thread."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        self._thread = None
