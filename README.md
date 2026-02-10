# Agent Autopsy & Failure Firewall

A lightweight toolkit to:
- **Record** agent runs (prompts, tool calls, env metadata)
- **Autopsy** failures with a forensic bundle (JSON traces + FS Diffs)
- **Firewall** against repeating known-bad plans (episodic memory + fuzzy/cosine similarity)

## Why
Agentic systems fail silently and repeat mistakes. This library gives you:
- A **flight recorder** (trace + context) you can replay.
- A **forensic diff** engine that shows exactly what changed on disk during a failure.
- A **failure firewall** that blocks plans semantically similar to past failures.

## Features
- **SQLite-backed store** for episodes (success/failure)
- **Forensic Diffs:** Captures unified diffs of file changes in CWD.
- **Semantic-Lite Similarity:** Uses pure-python Cosine Similarity on `task + plan` to block repeating bad plans.
- **CLI:** Inspect, list, and check episodes.

## Structure
- `src/autopsy/recorder.py` – flight recorder + diff engine
- `src/autopsy/store.py` – SQLite store + Cosine similarity engine
- `src/autopsy/trace.py` – Trace rendering (pretty print)
- `src/autopsy/cli.py` – CLI interface

## Usage
```python
from autopsy.recorder import Recorder

rec = Recorder(
    task="Optimize Database",
    plan="Rewrite indexes",
    similarity_method="cosine", # Use semantic-lite blocking
    min_similarity=0.7
)

with rec.session() as r:
    # Do work here...
    # If an exception is raised, it's recorded as a failure.
    # Future runs with similar plans will be BLOCKED.
    pass
```

## License
MIT
