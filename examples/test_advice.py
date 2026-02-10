from autopsy.recorder import Recorder, BlockedPlanError
import os

def main():
    # Clean old DB for testing
    db = os.path.expanduser("~/.autopsy/autopsy.db")
    if os.path.exists(db):
        os.remove(db)

    task = "Network Download"
    plan1 = "Fetch data from api.example.com"
    plan2 = "Retrieve data from api.example.com"
    
    print("--- FIRST RUN: TIMEOUT FAILURE ---")
    try:
        rec = Recorder(task=task, plan=plan1, similarity_method="cosine")
        with rec.session() as r:
            # Simulate a timeout
            raise TimeoutError("The connection timed out after 30s")
    except Exception as e:
        print(f"First run failed: {e}")

    print("\n--- SECOND RUN: BLOCKED WITH ADVICE ---")
    try:
        rec = Recorder(task=task, plan=plan2, similarity_method="cosine", min_similarity=0.7)
        with rec.session() as r:
            print("ERROR: This should have been blocked!")
    except BlockedPlanError as e:
        print(f"Second run BLOCKED as expected.")
        print(f"Firewall Output: {e}")

if __name__ == "__main__":
    main()
