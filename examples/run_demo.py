from autopsy.recorder import Recorder, BlockedPlanError


def risky_plan(n: int):
    # Deliberate failure when n < 0
    if n < 0:
        raise ValueError("n must be non-negative")
    return n * 2


def main():
    task = "double-number"
    plan = "double a number; fails if negative"

    # First run: will fail, but record the episode
    try:
        rec = Recorder(task=task, plan=plan, min_similarity=0.7)
        with rec.session() as r:
            r.log_event("input", {"n": -1})
            risky_plan(-1)
    except Exception as e:
        print(f"First run failed as expected: {e}")

    # Second run: blocked because prior failure is recorded (similar plan)
    try:
        rec = Recorder(task=task, plan="double number without checks", min_similarity=0.6)
        with rec.session() as r:
            r.log_event("input", {"n": -2})
            risky_plan(-2)
    except BlockedPlanError as e:
        print(f"Second run blocked by firewall: {e}")

    # Third run: adjust the plan, succeeds
    rec = Recorder(task=task, plan="double a number; check non-negative")
    with rec.session() as r:
        r.log_event("input", {"n": 4})
        out = risky_plan(4)
        r.log_event("output", {"result": out})
        print(f"Third run succeeded: {out}")


if __name__ == "__main__":
    main()
