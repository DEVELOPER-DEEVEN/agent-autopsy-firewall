import json
import os
from pathlib import Path

from autopsy.recorder import Recorder, BlockedPlanError


def test_block_on_repeat_failure(tmp_path: Path):
    db_path = tmp_path / "autopsy.db"
    run_dir = tmp_path / "runs"

    def fail():
        raise ValueError("boom")

    # first run: record failure
    try:
        rec = Recorder(task="t", plan="p", run_dir=str(run_dir), db_path=str(db_path))
        with rec.session() as r:
            r.log_event("step", {"x": 1})
            fail()
    except ValueError:
        pass

    # second run: should block
    try:
        rec = Recorder(task="t", plan="p", run_dir=str(run_dir), db_path=str(db_path))
        with rec.session() as r:
            r.log_event("step", {"x": 2})
            fail()
        assert False, "Should have blocked"
    except BlockedPlanError:
        assert True


def test_trace_written(tmp_path: Path):
    db_path = tmp_path / "autopsy.db"
    run_dir = tmp_path / "runs"

    rec = Recorder(task="t2", plan="p2", run_dir=str(run_dir), db_path=str(db_path))
    with rec.session() as r:
        r.log_event("step", {"x": 3})

    traces = list(run_dir.glob("trace-*.json"))
    assert traces, "Trace should be written"
    data = json.loads(traces[0].read_text())
    assert data["task"] == "t2"
    assert any(ev["kind"] == "env_snapshot" for ev in data["events"])
