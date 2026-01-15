"""
Utility functions and constants for Maisa Parser.
"""

from __future__ import annotations

import datetime

# HL7 v3 XML Namespaces
NS: dict[str, str] = {
    "v3": "urn:hl7-org:v3",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


def parse_date(date_str: str | None) -> str | None:
    """
    Parse an HL7 date string to ISO 8601 format.

    Args:
        date_str: HL7 formatted date (e.g., "YYYYMMDDHHMMSS+ZZZZ" or "YYYYMMDD").

    Returns:
        ISO 8601 formatted date string (e.g., "YYYY-MM-DDTHH:MM:SS"),
        the original string if parsing fails, or None if input is None/empty.
    """
    if not date_str:
        return None
    try:
        # Remove timezone suffix if present
        cleaned_date = date_str.split("+")[0]

        # Handle different precisions
        if len(cleaned_date) >= 14:
            dt = datetime.datetime.strptime(cleaned_date[:14], "%Y%m%d%H%M%S")
        elif len(cleaned_date) == 8:
            dt = datetime.datetime.strptime(cleaned_date, "%Y%m%d")
        else:
            return date_str

        return dt.isoformat()
    except ValueError:
        return date_str
