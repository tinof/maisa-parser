# Plan 02: Privacy Upgrade

> **Depends on**: [PLAN_01_PRODUCTION_READINESS.md](./PLAN_01_PRODUCTION_READINESS.md)  
> **Goal**: Add configurable privacy levels for safe data sharing  
> **Estimated effort**: 1.5-2 hours

---

## Executive Summary

This plan adds a `--privacy` flag with three levels to control PII exposure:
- **strict**: Maximum redaction for LLM upload safety
- **redacted** (default): Balanced - removes direct identifiers
- **full**: Everything included with warnings

---

## Privacy Levels Matrix

| Level | Flag | Use Case |
|-------|------|----------|
| `strict` | `--privacy strict` | Uploading to cloud LLMs (ChatGPT, Claude) |
| `redacted` | `--privacy redacted` (default) | Sharing with healthcare providers, research |
| `full` | `--privacy full` | Personal backup, local LLM analysis |

---

## Field-by-Field Redaction Matrix

| Field | `strict` | `redacted` (default) | `full` |
|-------|----------|----------------------|--------|
| `patient_profile.full_name` | `[REDACTED]` | `[REDACTED]` | ✓ |
| `patient_profile.national_id` | `[REDACTED]` | `[REDACTED]` | ✓ |
| `patient_profile.address` | `[REDACTED]` | `[REDACTED]` | ✓ |
| `patient_profile.phone` | `[REDACTED]` | `[REDACTED]` | ✓ |
| `patient_profile.email` | `[REDACTED]` | `[REDACTED]` | ✓ |
| `patient_profile.dob` | `[REDACTED]` | → `age: int` | ✓ |
| `patient_profile.gender` | ✓ | ✓ | ✓ |
| `encounters[].provider` | `[REDACTED]` | `[REDACTED]` | ✓ |
| `encounters[].notes` | `""` (dropped) | ✓ + warning | ✓ |
| `encounters[].date` | year-month only | ✓ | ✓ |
| All other timestamps | year-month only | ✓ | ✓ |
| Clinical data (meds, labs, dx) | ✓ | ✓ | ✓ |

---

## Task 1: Create Privacy Module

### File: `src/privacy.py`

```python
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
    
    STRICT = "strict"      # Maximum redaction - safe for cloud LLMs
    REDACTED = "redacted"  # Default - removes direct identifiers
    FULL = "full"          # No redaction - personal use only


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
    record: HealthRecord,
    level: PrivacyLevel = PrivacyLevel.REDACTED
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
        record.patient_profile = _redact_patient_profile(
            record.patient_profile, level
        )
    
    if record.encounters:
        record.encounters = [
            _redact_encounter(enc, level) for enc in record.encounters
        ]
    
    # Print appropriate warnings
    print_privacy_warning(level)
    
    return record


def _redact_patient_profile(
    profile: PatientProfile,
    level: PrivacyLevel
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
```

### Acceptance Criteria
- [ ] `PrivacyLevel` enum with STRICT, REDACTED, FULL
- [ ] `calculate_age()` handles edge cases (partial dates, None)
- [ ] `generalize_date()` truncates to year or year-month
- [ ] `apply_privacy()` creates deep copy, doesn't mutate original

---

## Task 2: Update Models

### File: `src/models.py`

Add `age` field to `PatientProfile`:

```python
class PatientProfile(BaseModel):
    """Patient demographic information."""
    
    full_name: str | None = None
    national_id: str | None = None  # Finnish henkilötunnus
    dob: str | None = None  # Date of birth (ISO format)
    age: int | None = None  # NEW: Computed when DOB is redacted
    gender: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
```

### Acceptance Criteria
- [ ] `age` field added with `int | None` type
- [ ] Field is optional (default None)
- [ ] Existing tests still pass

---

## Task 3: Update CLI

### File: `src/maisa_parser.py`

Add privacy flag and integration:

```python
from .privacy import PrivacyLevel, apply_privacy

# In argument parser:
parser.add_argument(
    "--privacy",
    type=str,
    choices=["strict", "redacted", "full"],
    default="redacted",
    help="Privacy level: strict (safest for LLMs), redacted (default), full (all PII)"
)

# In main(), after building health record:
def main() -> int:
    args = parse_args()
    # ... existing processing ...
    
    # Apply privacy transformations
    privacy_level = PrivacyLevel(args.privacy)
    health_record = apply_privacy(health_record, privacy_level)
    
    # Add privacy metadata to output
    output = {
        "_schema_version": "1.0.0",
        "_privacy_level": args.privacy,
        "_generated_at": datetime.utcnow().isoformat() + "Z",
        "health_record": health_record.model_dump()
    }
    
    # ... write output ...
```

### Acceptance Criteria
- [ ] `--privacy` flag accepts strict/redacted/full
- [ ] Default is "redacted"
- [ ] Output JSON includes `_privacy_level` metadata
- [ ] Privacy transformations applied before JSON serialization

---

## Task 4: Update Documentation

### File: `README.md`

Add new section after "Usage":

```markdown
## 🔐 Privacy & Data Safety

This tool processes **sensitive personal health information (PHI)**.
By default, output is **redacted** to reduce privacy risks.

### Privacy Levels

| Level | Command | What's Removed |
|-------|---------|----------------|
| `strict` | `--privacy strict` | All PII, provider names, notes dropped, dates → year-month |
| `redacted` | *(default)* | Direct identifiers, DOB → age, provider names |
| `full` | `--privacy full` | Nothing removed ⚠️ (includes henkilötunnus) |

### Examples

```bash
# Default (redacted) - safe for most sharing
maisa-parser /path/to/data -o health.json

# Strict - safe for cloud LLM upload
maisa-parser /path/to/data --privacy strict -o health.json

# Full - personal backup only
maisa-parser /path/to/data --privacy full -o health.json
```

### ⚠️ LLM Safety Warning

> **Before uploading to ChatGPT, Claude, or other cloud LLMs:**
> - Use `--privacy strict` mode
> - Even with redaction, **free-text notes may contain identifying information**
> - Consider using a **local LLM** (Ollama, LM Studio) for sensitive analysis

### For Maximum Safety

```bash
maisa-parser /path/to/data --privacy strict -o health_safe.json
```
```

### File: `README_fi.md`

Add Finnish translation:

```markdown
## 🔐 Tietosuoja ja tietoturva

Tämä työkalu käsittelee **arkaluonteisia henkilökohtaisia terveystietoja**.
Oletuksena tuloste on **anonymisoitu** tietosuojariskien vähentämiseksi.

### Tietosuojatasot

| Taso | Komento | Mitä poistetaan |
|------|---------|-----------------|
| `strict` | `--privacy strict` | Kaikki henkilötiedot, hoitajien nimet, muistiinpanot poistettu, päivämäärät → vuosi-kuukausi |
| `redacted` | *(oletus)* | Suorat tunnisteet, syntymäaika → ikä, hoitajien nimet |
| `full` | `--privacy full` | Mitään ei poisteta ⚠️ (sisältää henkilötunnuksen) |

### ⚠️ Tekoälypalveluiden varoitus

> **Ennen lataamista ChatGPT:hen, Claudeen tai muihin pilvipalveluihin:**
> - Käytä `--privacy strict` -tilaa
> - Vapaamuotoiset muistiinpanot voivat silti sisältää tunnistavia tietoja
> - Harkitse **paikallisen tekoälyn** käyttöä (Ollama, LM Studio)
```

### Acceptance Criteria
- [ ] README.md has Privacy section with table
- [ ] README_fi.md has Finnish translation
- [ ] LLM safety warning is prominent
- [ ] Examples show all three privacy levels

---

## Task 5: Add Privacy Tests

### File: `tests/test_privacy.py`

```python
"""Privacy transformation tests."""
import pytest
from datetime import date
from src.privacy import (
    PrivacyLevel,
    calculate_age,
    generalize_date,
    apply_privacy,
    REDACTED,
)
from src.models import HealthRecord, PatientProfile, DocumentSummary


class TestCalculateAge:
    """Tests for age calculation."""
    
    def test_full_date(self):
        """Calculate age from full DOB."""
        # Person born Jan 1, 2000
        age = calculate_age("2000-01-01")
        expected = date.today().year - 2000
        # Adjust if birthday hasn't happened yet this year
        if date.today() < date(date.today().year, 1, 1):
            expected -= 1
        assert age == expected
    
    def test_year_only(self):
        """Calculate age from year only."""
        age = calculate_age("1990")
        assert age == date.today().year - 1990
    
    def test_year_month(self):
        """Calculate age from year-month."""
        age = calculate_age("1985-06")
        assert age is not None
        assert 35 <= age <= 45  # Reasonable range
    
    def test_none_input(self):
        """Return None for None input."""
        assert calculate_age(None) is None
    
    def test_invalid_date(self):
        """Return None for invalid date."""
        assert calculate_age("not-a-date") is None


class TestGeneralizeDate:
    """Tests for date generalization."""
    
    def test_to_year_month(self):
        """Truncate to year-month."""
        assert generalize_date("2024-03-15", "year-month") == "2024-03"
    
    def test_to_year(self):
        """Truncate to year only."""
        assert generalize_date("2024-03-15", "year") == "2024"
    
    def test_none_input(self):
        """Return None for None input."""
        assert generalize_date(None) is None
    
    def test_short_date(self):
        """Handle already-short dates."""
        assert generalize_date("2024", "year-month") == "2024"


class TestApplyPrivacy:
    """Tests for privacy application."""
    
    @pytest.fixture
    def sample_record(self) -> HealthRecord:
        """Create a sample health record for testing."""
        return HealthRecord(
            patient_profile=PatientProfile(
                full_name="Matti Meikäläinen",
                national_id="010190-123A",
                dob="1990-01-01",
                gender="male",
                address="Mannerheimintie 1, Helsinki",
                phone="+358401234567",
                email="matti@example.fi",
            ),
            encounters=[
                DocumentSummary(
                    document_id="DOC001",
                    date="2024-03-15",
                    provider="Dr. Virtanen",
                    notes="Patient reports headache for 3 days.",
                )
            ],
            medications=[],
            allergies=[],
            lab_results=[],
            diagnoses=[],
        )
    
    def test_strict_redacts_all_pii(self, sample_record):
        """Strict mode redacts all PII fields."""
        result = apply_privacy(sample_record, PrivacyLevel.STRICT)
        
        assert result.patient_profile.full_name == REDACTED
        assert result.patient_profile.national_id == REDACTED
        assert result.patient_profile.dob == REDACTED
        assert result.patient_profile.address == REDACTED
        assert result.patient_profile.phone == REDACTED
        assert result.patient_profile.email == REDACTED
        # Gender should NOT be redacted
        assert result.patient_profile.gender == "male"
    
    def test_strict_drops_notes(self, sample_record):
        """Strict mode removes encounter notes."""
        result = apply_privacy(sample_record, PrivacyLevel.STRICT)
        
        assert result.encounters[0].notes == ""
    
    def test_strict_generalizes_dates(self, sample_record):
        """Strict mode truncates dates to year-month."""
        result = apply_privacy(sample_record, PrivacyLevel.STRICT)
        
        assert result.encounters[0].date == "2024-03"
    
    def test_redacted_converts_dob_to_age(self, sample_record):
        """Redacted mode converts DOB to age."""
        result = apply_privacy(sample_record, PrivacyLevel.REDACTED)
        
        assert result.patient_profile.dob == REDACTED
        assert result.patient_profile.age is not None
        assert result.patient_profile.age > 30  # Born 1990
    
    def test_redacted_keeps_notes(self, sample_record):
        """Redacted mode preserves notes."""
        result = apply_privacy(sample_record, PrivacyLevel.REDACTED)
        
        assert "headache" in result.encounters[0].notes
    
    def test_full_mode_no_changes(self, sample_record):
        """Full mode returns data unchanged."""
        result = apply_privacy(sample_record, PrivacyLevel.FULL)
        
        assert result.patient_profile.full_name == "Matti Meikäläinen"
        assert result.patient_profile.national_id == "010190-123A"
        assert result.encounters[0].notes == "Patient reports headache for 3 days."
    
    def test_original_unchanged(self, sample_record):
        """Original record should not be mutated."""
        original_name = sample_record.patient_profile.full_name
        
        apply_privacy(sample_record, PrivacyLevel.STRICT)
        
        assert sample_record.patient_profile.full_name == original_name
    
    def test_default_is_redacted(self, sample_record):
        """Default privacy level should be redacted."""
        result = apply_privacy(sample_record)  # No level specified
        
        assert result.patient_profile.full_name == REDACTED
        assert result.patient_profile.age is not None  # DOB -> age conversion


class TestCLIIntegration:
    """Test CLI privacy flag integration."""
    
    def test_privacy_flag_strict(self, tmp_path):
        """Verify --privacy strict flag works."""
        import subprocess
        from pathlib import Path
        
        fixture_dir = Path(__file__).parent / "fixtures"
        output = tmp_path / "output.json"
        
        result = subprocess.run(
            ["python", "-m", "src.maisa_parser", 
             str(fixture_dir), "-o", str(output),
             "--privacy", "strict"],
            capture_output=True, text=True
        )
        
        assert result.returncode == 0
        
        import json
        with open(output) as f:
            data = json.load(f)
        
        assert data.get("_privacy_level") == "strict"
```

### Acceptance Criteria
- [ ] All unit tests pass for privacy functions
- [ ] Edge cases covered (None, invalid dates, partial dates)
- [ ] Integration test verifies CLI flag
- [ ] Tests verify original record is not mutated

---

## Implementation Order

| # | Task | Dependencies | Effort |
|---|------|--------------|--------|
| 1 | Create `src/privacy.py` | Plan 01 complete | 25 min |
| 2 | Update `src/models.py` (add age field) | None | 5 min |
| 3 | Update `src/maisa_parser.py` (CLI + integration) | Tasks 1-2 | 15 min |
| 4 | Update `README.md` privacy section | None | 10 min |
| 5 | Update `README_fi.md` privacy section | Task 4 | 10 min |
| 6 | Create `tests/test_privacy.py` | Tasks 1-3 | 20 min |
| 7 | Run tests + LSP diagnostics | All above | 5 min |

---

## Verification Checklist

After implementation, verify:

```bash
# Test privacy levels
maisa-parser tests/fixtures/ --privacy strict -o /tmp/strict.json
maisa-parser tests/fixtures/ --privacy redacted -o /tmp/redacted.json
maisa-parser tests/fixtures/ --privacy full -o /tmp/full.json

# Verify redaction in strict mode
cat /tmp/strict.json | grep -c "REDACTED"  # Should be > 0
cat /tmp/strict.json | grep "national_id"  # Should show [REDACTED]

# Verify age calculation in redacted mode
cat /tmp/redacted.json | jq '.health_record.patient_profile.age'

# Run tests
pytest tests/test_privacy.py -v

# Type checking
mypy src/privacy.py
```

---

## Dependencies

This plan requires:
- ✅ Plan 01 completed (CLI entry point, logging infrastructure)
- ✅ `logging` module configured (for privacy warnings)
- ✅ Proper exit codes defined (for error handling)
