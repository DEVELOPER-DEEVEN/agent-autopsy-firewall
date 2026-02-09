import argparse
import json
import os
from typing import Optional

from .store import init_db, find_failures_like, DEFAULT_DB_PATH


def cmd_list(args):
    engine = init_db(args.db)
    from sqlmodel import Session, select
    from .store import Episode
    with Session(engine) as session:
        eps = session.exec(select(Episode).order_by(Episode.created_at.desc())).all()
        for ep in eps:
            print(f"[{ep.id}] {ep.created_at} | {ep.outcome} | {ep.task} | {ep.summary}")


def cmd_show(args):
    trace_path = args.trace
    if not os.path.exists(trace_path):
        print(f"Trace not found: {trace_path}")
        return
    with open(trace_path) as f:
        data = json.load(f)
    print(json.dumps(data, indent=2))


def cmd_check(args):
    matches = find_failures_like(args.task, args.plan, db_path=args.db, min_similarity=args.min_similarity)
    if not matches:
        print("No similar failures found.")
    else:
        for m in matches:
            ep = m.episode
            print(f"Match id={ep.id} similarity={m.similarity:.2f} outcome={ep.outcome} summary={ep.summary} trace={ep.trace_path}")


def build_parser():
    p = argparse.ArgumentParser(description="Agent Autopsy CLI")
    p.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to autopsy DB")
    sub = p.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="List episodes")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Show a trace JSON")
    p_show.add_argument("trace", help="Path to trace json")
    p_show.set_defaults(func=cmd_show)

    p_check = sub.add_parser("check", help="Check for similar failures")
    p_check.add_argument("task", help="Task description")
    p_check.add_argument("plan", help="Plan description")
    p_check.add_argument("--min-similarity", type=float, default=0.8, help="Similarity threshold")
    p_check.set_defaults(func=cmd_check)

    return p


def main(argv: Optional[list] = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
