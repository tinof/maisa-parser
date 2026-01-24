"""Privacy transformation module for Maisa Parser.

Provides configurable redaction levels for PHI (Protected Health Information)
to enable safe sharing of health records.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import HealthRecord, PatientProfile, DocumentSummary

logger = logging.getLogger(__name__)

REDACTED = "[REDACTED]"


class PrivacyLevel(str, Enum):
    """Privacy levels for output redaction."""

    STRICT = "strict"  # Maximum redaction - safe for cloud LLMs
    REDACTED = "redacted"  # Default - removes direct identifiers
    FULL = "full"  # No redaction - personal use only


# Fields to redact at each level
PII_FIELDS = {
    "full_name",
    "national_id",
    "address",
    "phone",
    "email",
}

PROVIDER_FIELDS = {
    "provider",
    "author",
    "performer",
}


def calculate_age(dob: str | None) -> int | None:
    """Calculate age from date of birth string.

    Args:
        dob: Date of birth in ISO format (YYYY-MM-DD) or partial (YYYY-MM, YYYY)

    Returns:
        Age in years, or None if DOB is invalid/missing
    """
    if not dob:
        return None

    try:
        # Handle partial dates
        if len(dob) == 4:  # YYYY
            birth_year = int(dob)
            return date.today().year - birth_year
        elif len(dob) == 7:  # YYYY-MM
            birth_date = datetime.strptime(dob, "%Y-%m").date()
        else:  # YYYY-MM-DD
            birth_date = datetime.strptime(dob[:10], "%Y-%m-%d").date()

        today = date.today()
        age = today.year - birth_date.year

        # Adjust if birthday hasn't occurred this year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1

        return age
    except (ValueError, TypeError):
        logger.warning("Could not parse DOB for age calculation: %s", dob)
        return None


def generalize_date(date_str: str | None, to: str = "year-month") -> str | None:
    """Generalize a date to reduce precision.

    Args:
        date_str: Date in ISO format
        to: Target precision - "year" or "year-month"

    Returns:
        Generalized date string, or None if input is None
    """
    if not date_str:
        return None

    try:
        if to == "year":
            return date_str[:4]
        elif to == "year-month":
            return date_str[:7] if len(date_str) >= 7 else date_str[:4]
        else:
            return date_str
    except (TypeError, IndexError):
        return None


def apply_privacy(
    record: HealthRecord, level: PrivacyLevel = PrivacyLevel.REDACTED
) -> HealthRecord:
    """Apply privacy transformations to a health record.

    Args:
        record: The health record to transform
        level: Privacy level to apply

    Returns:
        Transformed health record (deep copy, original unchanged)
    """
    # Full mode - return as-is with warning
    if level == PrivacyLevel.FULL:
        print_privacy_warning(level)
        return record

    # Create deep copy to avoid mutating original
    record = deepcopy(record)

    # Apply transformations based on level
    if record.patient_profile:
        record.patient_profile = _redact_patient_profile(record.patient_profile, level)

    if record.encounters:
        record.encounters = [_redact_encounter(enc, level) for enc in record.encounters]

    # Print appropriate warnings
    print_privacy_warning(level)

    return record


def _redact_patient_profile(
    profile: PatientProfile, level: PrivacyLevel
) -> PatientProfile:
    """Redact PII from patient profile."""
    from .models import PatientProfile

    data = profile.model_dump()

    # Redact PII fields
    for field in PII_FIELDS:
        if field in data and data[field]:
            data[field] = REDACTED

    # Handle DOB -> age conversion for redacted mode
    if level == PrivacyLevel.REDACTED:
        if data.get("dob"):
            data["age"] = calculate_age(data["dob"])
            data["dob"] = REDACTED
    elif level == PrivacyLevel.STRICT:
        data["dob"] = REDACTED
        data["age"] = None  # Don't expose even age in strict mode

    return PatientProfile.model_validate(data)


def _redact_encounter(encounter: DocumentSummary, level: PrivacyLevel):
    """Redact sensitive data from encounter/document summary."""
    from .models import DocumentSummary

    data = encounter.model_dump()

    # Redact provider fields
    for field in PROVIDER_FIELDS:
        if field in data and data[field]:
            data[field] = REDACTED

    if level == PrivacyLevel.STRICT:
        # Drop notes entirely
        if "notes" in data:
            data["notes"] = ""
        if "narrative" in data:
            data["narrative"] = ""

        # Generalize dates to year-month
        for field in ["date", "effective_time", "document_date"]:
            if field in data and data[field]:
                data[field] = generalize_date(data[field], "year-month")

    return DocumentSummary.model_validate(data)


def print_privacy_warning(level: PrivacyLevel) -> None:
    """Print privacy warnings to stderr based on level."""
    if level == PrivacyLevel.FULL:
        logger.warning("=" * 60)
        logger.warning("⚠️  PRIVACY WARNING: Full mode enabled")
        logger.warning("   Output contains ALL personal identifiers including:")
        logger.warning("   - Full name, national ID (henkilötunnus)")
        logger.warning("   - Address, phone, email")
        logger.warning("   - Unredacted clinical notes")
        logger.warning("   DO NOT upload to cloud services!")
        logger.warning("=" * 60)

    elif level == PrivacyLevel.REDACTED:
        logger.info("Privacy: redacted mode (default)")
        logger.info("Direct identifiers removed. Notes preserved.")
        logger.warning(
            "⚠️  Free-text notes may still contain identifying information. "
            "Use --privacy strict for cloud LLM upload."
        )

    elif level == PrivacyLevel.STRICT:
        logger.info("Privacy: strict mode enabled")
        logger.info("All PII removed. Notes dropped. Dates generalized.")
