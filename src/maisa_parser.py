"""
Maisa Parser - HL7 CDA XML to JSON Converter

Parses Clinical Document Architecture (CDA) XML files exported from the Maisa
patient portal (used by Apotti in Finland) and consolidates them into a
structured JSON format.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from lxml import etree

from .exceptions import InputError, OutputError, XMLParseError
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
from .privacy import PrivacyLevel, apply_privacy

__version__ = "1.0.0"
_SCHEMA_VERSION = "1.0.0"

logger = logging.getLogger(__name__)


def setup_logging(
    verbosity: int = 0, quiet: bool = False, json_format: bool = False
) -> None:
    """Configure logging based on verbosity level.

    Args:
        verbosity: 0=WARNING, 1=INFO, 2=DEBUG
        quiet: If True, suppress all output except errors
        json_format: If True, output JSON lines for pipeline consumption
    """
    if quiet:
        level = logging.ERROR
    else:
        level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}.get(
            verbosity, logging.DEBUG
        )

    if json_format:
        format_str = '{"time":"%(asctime)s","level":"%(levelname)s","module":"%(module)s","message":"%(message)s"}'
    else:
        format_str = "%(levelname)s: %(message)s"

    logging.basicConfig(level=level, format=format_str, force=True)


def process_files(
    data_dir: str, output_file: str, summary_file: str, fail_fast: bool = False
) -> HealthRecord:
    """
    Process all CDA XML files in a directory and generate consolidated JSON.

    Reads the summary file (default: DOC0001.XML) for structured clinical
    data (patient profile, medications, labs, diagnoses, allergies), then
    scans all DOC*.XML files for encounter narratives.

    Args:
        data_dir: Directory containing the XML files.
        output_file: Path for the output JSON file.
        summary_file: Name of the summary XML file (e.g., "DOC0001.XML").
        fail_fast: If True, stop on first error.

    Returns:
        The populated HealthRecord.

    Raises:
        InputError: If directory doesn't exist or has no XML files.
        XMLParseError: If XML parsing fails.
        OutputError: If output file cannot be written.
    """
    if not os.path.exists(data_dir):
        raise InputError(f"Directory not found: {data_dir}")

    # Only process DOC*.XML files (exclude METADATA.XML and other non-clinical files)
    files = [
        f
        for f in os.listdir(data_dir)
        if f.upper().endswith(".XML") and f.upper().startswith("DOC")
    ]
    files.sort()

    if not files:
        raise InputError(f"No XML files found in: {data_dir}")

    record = HealthRecord()

    # Process Summary File (defaults to DOC0001.XML) specifically for the "Dashboard" data
    doc0001_path = os.path.join(data_dir, summary_file)
    if os.path.exists(doc0001_path):
        logger.info("Processing summary file: %s", doc0001_path)
        try:
            tree = etree.parse(doc0001_path)
            root = tree.getroot()

            record.patient_profile = extract_patient_profile(root)
            record.clinical_summary.allergies = extract_allergies(root)

            meds = extract_medications(root)
            # Separate active vs history (simple logic based on status or date)
            for m in meds:
                if m.status == "active" or (m.end_date is None):
                    record.clinical_summary.active_medications.append(m)
                else:
                    record.clinical_summary.medication_history.append(m)

            logger.debug(
                "Extracted %d active medications",
                len(record.clinical_summary.active_medications),
            )

            record.lab_results = extract_lab_results(root)
            logger.debug("Extracted %d lab results", len(record.lab_results))

            record.diagnoses = extract_diagnoses(root)
            logger.debug("Extracted %d diagnoses", len(record.diagnoses))

            record.procedures = extract_procedures(root)
            record.immunizations = extract_immunizations(root)
            record.social_history = extract_social_history(root)

        except etree.XMLSyntaxError as e:
            if fail_fast:
                raise XMLParseError(str(e), filename=doc0001_path) from e
            logger.error("XML parse error in %s: %s", doc0001_path, e)
        except Exception as e:
            if fail_fast:
                raise XMLParseError(str(e), filename=doc0001_path) from e
            logger.error("Failed to process summary file %s: %s", doc0001_path, e)
    else:
        logger.warning("Summary file not found: %s", doc0001_path)

    # Now iterate ALL files for Encounters/Notes
    logger.info("Processing %d files for encounters/notes...", len(files))
    all_encounters: list[Any] = []

    for f in files:
        f_path = os.path.join(data_dir, f)
        try:
            doc_summary = extract_document_summary(f_path)
            if doc_summary:
                all_encounters.append(doc_summary)
        except Exception as e:
            if fail_fast:
                raise XMLParseError(str(e), filename=f_path) from e
            logger.warning("Skipping %s due to error: %s", f, e)

    # Sort encounters by date
    all_encounters.sort(key=lambda x: x.date if x.date else "1900-01-01", reverse=True)
    record.encounters = all_encounters
    logger.info("Extracted %d encounters", len(all_encounters))

    return record


def write_output(
    record: HealthRecord, output_file: str, privacy_level: str = "redacted"
) -> None:
    """Write health record to JSON file with metadata.

    Args:
        record: The health record to write.
        output_file: Path to output file.
        privacy_level: Privacy level applied.

    Raises:
        OutputError: If file cannot be written.
    """
    output = {
        "_schema_version": _SCHEMA_VERSION,
        "_privacy_level": privacy_level,
        "_generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "_generator": f"maisa-parser/{__version__}",
        "health_record": record.model_dump(),
    }

    try:
        with open(output_file, "w", encoding="utf-8") as out_f:
            json.dump(output, out_f, indent=2, ensure_ascii=False)
        logger.info("Output written to %s", output_file)
    except OSError as e:
        raise OutputError(f"Failed to write output file: {e}") from e


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Parse Maisa/Apotti HL7 CDA XML files into a JSON history.",
        prog="maisa-parser",
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
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v=INFO, -vv=DEBUG)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress all output except errors",
    )
    parser.add_argument(
        "--log-format",
        choices=["text", "json"],
        default="text",
        help="Log output format (default: text)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first error (default: continue and report)",
    )
    parser.add_argument(
        "--privacy",
        type=str,
        choices=["strict", "redacted", "full"],
        default="redacted",
        help="Privacy level: strict (safest for LLMs), redacted (default), full (all PII)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """Main entry point. Returns exit code."""
    from .exceptions import (
        ExtractionError,
        InputError,
        MaisaParserError,
        OutputError,
        XMLParseError,
    )

    try:
        parsed_args = parse_args(args)
        setup_logging(
            verbosity=parsed_args.verbose,
            quiet=parsed_args.quiet,
            json_format=parsed_args.log_format == "json",
        )

        # Validate input directory
        if not os.path.exists(parsed_args.directory):
            raise InputError(f"Directory not found: {parsed_args.directory}")

        if not os.path.isdir(parsed_args.directory):
            raise InputError(f"Not a directory: {parsed_args.directory}")

        # Process files
        record = process_files(
            data_dir=parsed_args.directory,
            output_file=parsed_args.output,
            summary_file=parsed_args.summary_file,
            fail_fast=parsed_args.fail_fast,
        )

        # Apply privacy transformations
        privacy_level = PrivacyLevel(parsed_args.privacy)
        record = apply_privacy(record, privacy_level)

        # Write output
        write_output(
            record=record,
            output_file=parsed_args.output,
            privacy_level=parsed_args.privacy,
        )

        return 0

    except InputError as e:
        logger.error("Input error: %s", e)
        return e.exit_code
    except XMLParseError as e:
        logger.error("Parse error: %s", e)
        return e.exit_code
    except ExtractionError as e:
        logger.error("Extraction error: %s", e)
        return e.exit_code
    except OutputError as e:
        logger.error("Output error: %s", e)
        return e.exit_code
    except MaisaParserError as e:
        logger.error("Error: %s", e)
        return e.exit_code
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
