from autopsy.recorder import Recorder, BlockedPlanError
import os
from autopsy.store import cosine_similarity_pure

def main():
    # Clean old DB for testing
    db = os.path.expanduser("~/.autopsy/autopsy.db")
    if os.path.exists(db):
        os.remove(db)

    task = "Process JSON data"
    plan1 = "Parse the json file and extract values"
    plan2 = "JSON parsing and extraction of data"
    
    sim = cosine_similarity_pure(f"{task} {plan1}", f"{task} {plan2}")
    print(f"DEBUG: Cosine Similarity between episodes: {sim:.4f}")

    # First run: Fails
    try:
        rec = Recorder(task=task, plan=plan1, similarity_method="cosine")
        with rec.session() as r:
            raise ValueError("Corrupt JSON structure detected")
    except Exception as e:
        print(f"First run failed: {e}")

    # Second run
    try:
        # Lowering threshold slightly for testing
        rec = Recorder(task=task, plan=plan2, similarity_method="cosine", min_similarity=0.5)
        with rec.session() as r:
            print("ERROR: This should have been blocked!")
    except BlockedPlanError as e:
        print(f"Second run BLOCKED as expected: {e}")

if __name__ == "__main__":
    main()
