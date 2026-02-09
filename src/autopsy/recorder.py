import json
import os
import time
import traceback
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from .store import record_episode, find_failures_like, DEFAULT_DB_PATH


class BlockedPlanError(Exception):
    """Raised when a plan is blocked due to prior failure."""


def snapshot_env(max_files: int = 50) -> Dict[str, Any]:
    """Capture a lightweight env snapshot (cwd listing + env vars)."""
    cwd = os.getcwd()
    files = []
    try:
        for idx, name in enumerate(sorted(os.listdir(cwd))):
            if idx >= max_files:
                break
            try:
                stat = os.stat(name)
                files.append({"name": name, "size": stat.st_size, "mtime": stat.st_mtime})
            except OSError:
                files.append({"name": name, "error": "stat_failed"})
    except Exception:
        files.append({"error": "listdir_failed"})
    env_vars = {k: v for k, v in os.environ.items() if k.startswith("APP_") or k.startswith("ENV_")}
    return {"cwd": cwd, "files": files, "env": env_vars}


class Recorder:
    def __init__(self, task: str, plan: str, run_dir: Optional[str] = None, db_path: str = DEFAULT_DB_PATH, min_similarity: float = 0.8):
        self.task = task
        self.plan = plan
        self.events: List[Dict[str, Any]] = []
        self.run_dir = run_dir or os.path.expanduser("~/.autopsy/runs")
        self.db_path = db_path
        self.min_similarity = min_similarity
        os.makedirs(self.run_dir, exist_ok=True)

    def log_event(self, kind: str, detail: Dict[str, Any]):
        self.events.append({"ts": time.time(), "kind": kind, "detail": detail})

    @contextmanager
    def session(self):
        # Block if similar failure exists
        failures = find_failures_like(self.task, self.plan, db_path=self.db_path, min_similarity=self.min_similarity)
        if failures:
            raise BlockedPlanError(f"Plan blocked; prior failures: {[(m.episode.id, round(m.similarity, 2)) for m in failures]}")

        trace_path = os.path.join(self.run_dir, f"trace-{int(time.time())}.json")
        start = time.time()
        self.log_event("env_snapshot", snapshot_env())
        try:
            yield self
            duration = time.time() - start
            summary = f"Completed in {duration:.2f}s"
            self._persist(trace_path, outcome="success", summary=summary)
        except Exception as e:
            duration = time.time() - start
            summary = f"Failed in {duration:.2f}s: {e}"
            self.log_event("exception", {"err": repr(e), "trace": traceback.format_exc()})
            self._persist(trace_path, outcome="failure", summary=summary)
            raise

    def _persist(self, trace_path: str, outcome: str, summary: str):
        with open(trace_path, "w") as f:
            json.dump({
                "task": self.task,
                "plan": self.plan,
                "outcome": outcome,
                "summary": summary,
                "events": self.events,
            }, f, indent=2)
        record_episode(task=self.task, plan=self.plan, outcome=outcome, summary=summary, trace_path=trace_path, db_path=self.db_path)
