"""
Maisa Parser - HL7 CDA XML to JSON Converter

Parses Clinical Document Architecture (CDA) XML files exported from the Maisa
patient portal (used by Apotti in Finland) and consolidates them into a
structured JSON format.
"""

from __future__ import annotations

import argparse
import os
from typing import Any

from lxml import etree

from .extractors import (
    extract_allergies,
    extract_diagnoses,
    extract_document_summary,
    extract_immunizations,
    extract_lab_results,
    extract_medications,
    extract_patient_profile,
    extract_procedures,
    extract_social_history,
)
from .models import HealthRecord


def process_files(data_dir: str, output_file: str, summary_file: str) -> None:
    """
    Process all CDA XML files in a directory and generate consolidated JSON.

    Reads the summary file (default: DOC0001.XML) for structured clinical
    data (patient profile, medications, labs, diagnoses, allergies), then
    scans all DOC*.XML files for encounter narratives.

    Args:
        data_dir: Directory containing the XML files.
        output_file: Path for the output JSON file.
        summary_file: Name of the summary XML file (e.g., "DOC0001.XML").
    """
    files = [f for f in os.listdir(data_dir) if f.upper().endswith(".XML")]
    files.sort()

    record = HealthRecord()

    # Process Summary File (defaults to DOC0001.XML) specifically for the "Dashboard" data
    doc0001_path = os.path.join(data_dir, summary_file)
    if os.path.exists(doc0001_path):
        print(f"Processing Summary {doc0001_path}...")
        try:
            tree = etree.parse(doc0001_path)
            root = tree.getroot()

            record.patient_profile = extract_patient_profile(root)
            record.clinical_summary.allergies = extract_allergies(root)

            meds = extract_medications(root)
            # Separate active vs history (simple logic based on status or date)
            # Schema expects separation
            for m in meds:
                if m.status == "active" or (m.end_date is None):
                    record.clinical_summary.active_medications.append(m)
                else:
                    record.clinical_summary.medication_history.append(m)

            record.lab_results = extract_lab_results(root)
            record.diagnoses = extract_diagnoses(root)
            record.procedures = extract_procedures(root)
            record.immunizations = extract_immunizations(root)
            record.social_history = extract_social_history(root)

        except Exception as e:
            print(f"Failed to process summary file {doc0001_path}: {e}")

    # Now iterate ALL files (including DOC0001 if desired, but primarily others) for Encounters/Notes
    print("Processing all files for Encounters/Notes...")
    all_encounters: list[
        Any
    ] = []  # Using Any to avoid circular import issues if type needed

    for f in files:
        f_path = os.path.join(data_dir, f)
        doc_summary = extract_document_summary(f_path)
        if doc_summary:
            all_encounters.append(doc_summary)

    # Sort encounters by date
    all_encounters.sort(key=lambda x: x.date if x.date else "1900-01-01", reverse=True)
    record.encounters = all_encounters

    # Write output
    try:
        with open(output_file, "w", encoding="utf-8") as out_f:
            out_f.write(record.model_dump_json(indent=2))
        print(f"Successfully generated {output_file}")
    except Exception as e:
        print(f"Error writing output file: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse Maisa/Apotti HL7 CDA XML files into a JSON history."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory containing the XML files (default: current directory)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="patient_history.json",
        help="Output JSON file path (default: patient_history.json)",
    )
    parser.add_argument(
        "--summary-file",
        default="DOC0001.XML",
        help="Name of the summary XML file (default: DOC0001.XML)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.directory):
        print(f"Error: Directory '{args.directory}' not found.")
        exit(1)

    process_files(args.directory, args.output, args.summary_file)
