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
from src.models import HealthRecord, PatientProfile, DocumentSummary, ClinicalSummary


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
