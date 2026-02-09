# Agent Autopsy & Failure Firewall

A lightweight toolkit to:
- **Record** agent runs (prompts, tool calls, env metadata)
- **Autopsy** failures with a forensic bundle
- **Firewall** against repeating known-bad plans (episodic memory)

## Why
Agentic systems fail silently and repeat mistakes. This library gives you:
- A **flight recorder** (trace + context) you can replay.
- A **failure firewall** that blocks plans similar to past failures.

## Features (MVP)
- SQLite-backed store for episodes (success/failure)
- Recorder context manager to log steps/events
- Failure firewall: block on similar signature; suggest alternates
- Forensic bundle: JSON trace + hashed signature

## Roadmap
- Replay UI (web) for traces
- Attach filesystem/network diffs
- Heuristics for similarity (LLM + embeddings)
- CI hook to fail on regression traces

## Quickstart
```bash
pip install -r requirements.txt
python examples/run_demo.py
```

## Structure
- `src/autopsy/recorder.py` – flight recorder
- `src/autopsy/firewall.py` – episodic failure firewall
- `src/autopsy/store.py` – SQLite store
- `examples/run_demo.py` – demo of recording + blocking repeat failure

## License
MIT
