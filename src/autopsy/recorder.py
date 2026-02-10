import json
import os
import time
import traceback
import difflib
import re
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Set

from .store import record_episode, find_failures_like, DEFAULT_DB_PATH


class BlockedPlanError(Exception):
    """Raised when a plan is blocked due to prior failure."""


def classify_failure(err_msg: str) -> str:
    """Categorize the failure based on common error patterns."""
    patterns = {
        "TIMEOUT": [r"timeout", r"timed out", r"deadline"],
        "PERMISSION": [r"permission denied", r"403", r"access denied", r"unauthorized"],
        "VALIDATION": [r"validation error", r"invalid", r"pydantic", r"schema mismatch"],
        "NETWORK": [r"connection failed", r"dns", r"502", r"503", r"504", r"socket error"],
        "NOT_FOUND": [r"not found", r"404", r"no such file"],
        "LOGIC": [r"assertionerror", r"logic error", r"valueerror", r"typeerror"]
    }
    
    msg_lower = err_msg.lower()
    for kind, regexes in patterns.items():
        if any(re.search(r, msg_lower) for r in regexes):
            return kind
    return "UNKNOWN"


def get_surgical_advice(kind: str) -> str:
    """Provide actionable advice for a specific failure kind."""
    advice = {
        "TIMEOUT": "Consider increasing the timeout parameter or checking system load.",
        "PERMISSION": "Verify file permissions, environment variables, or API tokens.",
        "VALIDATION": "Check if the input schema has changed or if required fields are missing.",
        "NETWORK": "Check connectivity or retry with an exponential backoff.",
        "NOT_FOUND": "Verify file paths or endpoint URLs. Ensure dependent resources exist.",
        "LOGIC": "Review the core algorithm. Add more logging to trace the state transition.",
        "UNKNOWN": "Perform a deep autopsy using the trace logs and filesystem diffs."
    }
    return advice.get(kind, advice["UNKNOWN"])


def snapshot_env(max_files: int = 50) -> dict[str, Any]:
    """Capture a lightweight env snapshot (cwd listing + env vars)."""
    cwd = os.getcwd()
    files = []
    try:
        for idx, name in enumerate(sorted(os.listdir(cwd))):
            if idx >= max_files:
                break
            if os.path.isdir(name):
                continue
            try:
                stat = os.stat(name)
                files.append({"name": name, "size": stat.st_size, "mtime": stat.st_mtime})
            except OSError:
                files.append({"name": name, "error": "stat_failed"})
    except Exception:
        files.append({"error": "listdir_failed"})
    env_vars = {k: v for k, v in os.environ.items() if k.startswith("APP_") or k.startswith("ENV_")}
    return {"cwd": cwd, "files": files, "env": env_vars}


def get_file_contents(max_size: int = 1024 * 50) -> Dict[str, str]:
    """Get contents of small text files in CWD for diffing."""
    contents = {}
    for name in os.listdir(os.getcwd()):
        if not os.path.isfile(name) or name.startswith("."):
            continue
        try:
            if os.path.getsize(name) > max_size:
                continue
            with open(name, "r", errors="replace") as f:
                contents[name] = f.read()
        except Exception:
            continue
    return contents


class Recorder:
    def __init__(
        self, 
        task: str, 
        plan: str, 
        run_dir: Optional[str] = None, 
        db_path: str = DEFAULT_DB_PATH, 
        min_similarity: float = 0.8,
        similarity_method: str = "fuzzy"
    ):
        self.task = task
        self.plan = plan
        self.events: list[dict[str, Any]] = []
        self.run_dir = run_dir or os.path.expanduser("~/.autopsy/runs")
        self.db_path = db_path
        self.min_similarity = min_similarity
        self.similarity_method = similarity_method
        self.before_files: Dict[str, str] = {}
        os.makedirs(self.run_dir, exist_ok=True)

    def log_event(self, kind: str, detail: dict[str, Any]):
        self.events.append({"ts": time.time(), "kind": kind, "detail": detail})

    @contextmanager
    def session(self, capture_diffs: bool = True):
        # Block if similar failure exists
        failures = find_failures_like(
            self.task, 
            self.plan, 
            db_path=self.db_path, 
            min_similarity=self.min_similarity,
            method=self.similarity_method
        )
        if failures:
            best_match = failures[0]
            advice = get_surgical_advice(best_match.episode.failure_kind or "UNKNOWN")
            error_msg = (
                f"Plan blocked (Sim={best_match.similarity:.2f}). "
                f"Past failure: {best_match.episode.failure_kind}. "
                f"Advice: {advice}"
            )
            raise BlockedPlanError(error_msg)

        if capture_diffs:
            self.before_files = get_file_contents()

        trace_path = os.path.join(self.run_dir, f"trace-{int(time.time())}.json")
        start = time.time()
        self.log_event("env_snapshot", snapshot_env())
        
        try:
            yield self
            duration = time.time() - start
            
            if capture_diffs:
                self._capture_diffs()
                
            summary = f"Completed in {duration:.2f}s"
            self._persist(trace_path, outcome="success", summary=summary)
        except Exception as e:
            duration = time.time() - start
            err_msg = str(e)
            failure_kind = classify_failure(err_msg)
            
            if capture_diffs:
                self._capture_diffs()
                
            summary = f"Failed in {duration:.2f}s: {err_msg}"
            self.log_event("exception", {"kind": failure_kind, "err": err_msg, "trace": traceback.format_exc()})
            self._persist(trace_path, outcome="failure", summary=summary, failure_kind=failure_kind)
            raise

    def _capture_diffs(self):
        after_files = get_file_contents()
        all_keys = set(self.before_files.keys()) | set(after_files.keys())
        diffs = []
        
        for name in all_keys:
            before = self.before_files.get(name, "").splitlines()
            after = after_files.get(name, "").splitlines()
            
            if before != after:
                delta = list(difflib.unified_diff(before, after, fromfile=f"a/{name}", tofile=f"b/{name}", lineterm=""))
                if delta:
                    diffs.append({"file": name, "diff": "\n".join(delta)})
        
        if diffs:
            self.log_event("fs_diff", {"changes": diffs})

    def _persist(self, trace_path: str, outcome: str, summary: str, failure_kind: Optional[str] = None):
        with open(trace_path, "w") as f:
            json.dump({
                "task": self.task,
                "plan": self.plan,
                "outcome": outcome,
                "failure_kind": failure_kind,
                "summary": summary,
                "events": self.events,
            }, f, indent=2)
        record_episode(
            task=self.task, 
            plan=self.plan, 
            outcome=outcome, 
            summary=summary, 
            trace_path=trace_path, 
            failure_kind=failure_kind,
            db_path=self.db_path
        )
