"""
Utility functions and constants for Maisa Parser.
"""

from __future__ import annotations

import datetime
import re

# HL7 v3 XML Namespaces
NS: dict[str, str] = {
    "v3": "urn:hl7-org:v3",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


def date_digits(date_str: str | None) -> str:
    """Return the date/time digits of an HL7 or ISO 8601 date, without time zone.

    "20261105-0500" -> "20261105", "2026-11-05T12:00:00" -> "20261105120000",
    "202611" -> "202611". Returns "" when no date digits are found.
    """
    if not date_str:
        return ""
    s = date_str.strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        # ISO 8601 (as produced by parse_date): drop separators and any offset
        s = s[:19].replace("-", "").replace(":", "").replace("T", "")
    match = re.match(r"\d+", s)
    return match.group(0)[:14] if match else ""


def same_date_prefix(a: str | None, b: str | None, min_len: int = 4) -> bool:
    """True when two dates agree at the precision both share (at least ``min_len`` digits)."""
    da, db = date_digits(a), date_digits(b)
    n = min(len(da), len(db), 8)
    return n >= min_len and da[:n] == db[:n]


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
