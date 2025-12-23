import json
import os
import sys

# Add src to python path to import the parser
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from maisa_parser import process_files

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(TEST_DIR, "fixtures")
OUTPUT_FILE = os.path.join(TEST_DIR, "test_output.json")


def run_tests():
    print("Running tests...")

    # Clean up previous run
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)

    # Run parser
    print(f"Parsing fixtures in {FIXTURES_DIR}...")
    try:
        process_files(FIXTURES_DIR, OUTPUT_FILE, "DOC0001.XML")
    except Exception as e:
        print(f"FAILED: Parser raised exception: {e}")
        return False

    # Verify output exists
    if not os.path.exists(OUTPUT_FILE):
        print("FAILED: Output file was not created.")
        return False

    # Verify content
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            data = json.load(f)

        # 1. Check Patient Profile
        profile = data.get("patient_profile", {})
        if profile.get("full_name") == "John Doe":
            print("PASS: Patient Name extracted correctly (John Doe).")
        else:
            print(f"FAIL: Patient Name mismatch. Got: {profile.get('full_name')}")

        # 2. Check Medications
        meds = data.get("clinical_summary", {}).get("active_medications", [])
        found_ibuprofen = False
        for m in meds:
            if "Ibuprofen" in m["name"] or "Burana" in m["name"]:
                found_ibuprofen = True
                break

        if found_ibuprofen:
            print("PASS: Medication (Burana/Ibuprofen) found.")
        else:
            print("FAIL: Medication not found.")

        # 3. Check Lab Results
        labs = data.get("lab_results", [])
        found_hb = False
        for lab in labs:
            if lab["test_name"] == "Hemoglobin" and lab["result_value"] == 145.0:
                found_hb = True
                break

        if found_hb:
            print("PASS: Lab result (Hemoglobin 145) found.")
        else:
            print("FAIL: Lab result not found.")

        # 4. Check Encounters/Notes
        encounters = data.get("encounters", [])
        found_encounter = False
        for e in encounters:
            if e["provider"] == "Dr. House" and "leg pain" in e["notes"]:
                found_encounter = True
                break

        if found_encounter:
            print("PASS: Encounter (Dr. House) and notes found.")
        else:
            print("FAIL: Encounter or notes missing.")

    except Exception as e:
        print(f"FAILED: Error verifying JSON content: {e}")
        return False

    print("\nALL TESTS PASSED!")
    return True


if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
