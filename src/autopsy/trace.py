import json
import time
from pathlib import Path
from typing import Dict, Any


def load_trace(path: str | Path) -> Dict[str, Any]:
    with open(path, "r") as f:
        return json.load(f)


def render_trace(trace: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"Task: {trace.get('task')}")
    lines.append(f"Plan: {trace.get('plan')}")
    lines.append(f"Outcome: {trace.get('outcome')} | {trace.get('summary')}")
    events = trace.get("events", [])
    for ev in events:
        ts = ev.get("ts", 0)
        ts_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
        kind = ev.get("kind")
        detail = ev.get("detail")
        
        if kind == "fs_diff":
            lines.append(f"[{ts_str}] {kind}:")
            for change in detail.get("changes", []):
                lines.append(f"  --- {change['file']} ---")
                lines.append(change['diff'])
        else:
            lines.append(f"[{ts_str}] {kind}: {detail}")
            
    return "\n".join(lines)
