"""Unit tests for extractor fixes, built on the structures real Apotti exports use.

All XML here is synthetic.
"""

from pathlib import Path

import pytest
from lxml import etree

from src.extractors import (
    extract_document_summary,
    extract_lab_results,
    extract_medications,
    is_active_medication,
)
from src.maisa_parser import process_files
from src.models import Medication
from src.utils import date_digits

HEADER = """<ClinicalDocument xmlns="urn:hl7-org:v3"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <title>Test document</title>
  <effectiveTime value="20261110120000+0200"/>
  <recordTarget><patientRole><patient>
    <birthTime value="{birth}"/>
  </patient></patientRole></recordTarget>
  {extra_header}
  <component><structuredBody>{body}</structuredBody></component>
</ClinicalDocument>"""


def _doc(body: str = "", extra_header: str = "", birth: str = "19500101") -> str:
    return HEADER.format(body=body, extra_header=extra_header, birth=birth)


def _root(body: str) -> etree._Element:
    return etree.fromstring(_doc(body).encode())


def _med_entry(name: str, status_code: str | None, high: str | None = None) -> str:
    status_obs = ""
    if status_code:
        status_obs = f"""<entryRelationship typeCode="REFR"><observation classCode="OBS" moodCode="EVN">
              <code code="33999-4" codeSystem="2.16.840.1.113883.6.1"/>
              <value xsi:type="CE" code="{status_code}" codeSystem="2.16.840.1.113883.6.96"/>
            </observation></entryRelationship>"""
    high_el = f'<high value="{high}"/>' if high else '<high nullFlavor="UNK"/>'
    return f"""<entry><substanceAdministration classCode="SBADM" moodCode="INT">
          <statusCode code="completed"/>
          <effectiveTime xsi:type="IVL_TS"><low value="20240101"/>{high_el}</effectiveTime>
          <consumable><manufacturedProduct><manufacturedMaterial>
            <code displayName="{name}"/>
          </manufacturedMaterial></manufacturedProduct></consumable>
          {status_obs}
        </substanceAdministration></entry>"""


MED_SECTION = """<component><section><code code="10160-0"/>{entries}</section></component>"""
IMMUNIZATION_SECTION = """<component><section><code code="11369-6"/>
  <entry><substanceAdministration classCode="SBADM" moodCode="EVN">
    <statusCode code="completed"/>
    <effectiveTime value="20240301"/>
    <consumable><manufacturedProduct><manufacturedMaterial>
      <code displayName="Test vaccine"/>
    </manufacturedMaterial></manufacturedProduct></consumable>
  </substanceAdministration></entry>
</section></component>"""


def test_immunizations_are_not_medications():
    body = MED_SECTION.format(entries=_med_entry("Drug A", "55561003")) + IMMUNIZATION_SECTION
    names = [m.name for m in extract_medications(_root(body))]
    assert names == ["Drug A"]


def test_medication_status_comes_from_status_observation():
    entries = (
        _med_entry("Active drug", "55561003")
        + _med_entry("Stopped drug", "73425007")
        + _med_entry("Paused drug", "421139008")
        + _med_entry("No status drug", None)
    )
    meds = {
        m.name: m.status for m in extract_medications(_root(MED_SECTION.format(entries=entries)))
    }
    assert meds == {
        "Active drug": "active",
        "Stopped drug": "inactive",
        "Paused drug": "on hold",
        "No status drug": "completed",
    }


def test_is_active_medication():
    as_of = "2026-11-10T12:00:00"
    # Clinical status wins over the end date
    assert is_active_medication(Medication(name="a", status="active", end_date="2020-01-01"), as_of)
    assert not is_active_medication(Medication(name="b", status="inactive"), as_of)
    # Without a clinical status, compare the end date with the document date
    assert is_active_medication(Medication(name="c", status="completed"), as_of)
    assert is_active_medication(
        Medication(name="d", status="completed", end_date="2027-01-01T00:00:00"), as_of
    )
    assert not is_active_medication(
        Medication(name="e", status="completed", end_date="2025-01-01T00:00:00"), as_of
    )


@pytest.mark.parametrize(
    ("status", "end_date", "as_of", "expected"),
    [
        # Raw HL7 end dates of other precisions, which parse_date returns unchanged
        ("completed", "202611011200", "2026-11-10T12:00:00", False),
        ("completed", "202601", "2026-11-10T12:00:00", False),
        ("completed", "20261105-0500", "2026-11-10T12:00:00", False),
        ("completed", "2026", "2026-11-10T12:00:00", True),  # same year: keep active
        ("completed", "2026-12-01T00:00:00", "202611101200", True),
        # Unreadable dates never hide a medication in history
        ("completed", "2025-01-01T00:00:00", None, True),
        ("completed", "garbage", "2026-11-10T12:00:00", True),
        # HL7 ActStatus values that mean the medication is not in use
        ("aborted", None, "2026-11-10T12:00:00", False),
        ("cancelled", None, "2026-11-10T12:00:00", False),
        ("nullified", None, "2026-11-10T12:00:00", False),
        # On hold: decided by the end date like an entry without a clinical status
        ("on hold", None, "2026-11-10T12:00:00", True),
        ("on hold", "2025-01-01T00:00:00", "2026-11-10T12:00:00", False),
    ],
)
def test_is_active_medication_edge_cases(status, end_date, as_of, expected):
    med = Medication(name="x", status=status, end_date=end_date)
    assert is_active_medication(med, as_of) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("20261105-0500", "20261105"),
        ("20261105120000+0200", "20261105120000"),
        ("2026-11-05T12:00:00", "20261105120000"),
        ("202611", "202611"),
        (None, ""),
        ("Unknown", ""),
    ],
)
def test_date_digits(value, expected):
    assert date_digits(value) == expected


def _lab_obs(value: str, ref_range: str) -> str:
    return f"""<entry><observation classCode="OBS" moodCode="EVN">
      <code code="1" displayName="B -Leuk"/>
      <effectiveTime value="20260101080000+0200"/>
      <value xsi:type="PQ" value="{value}" unit="E9/l"/>
      {ref_range}
    </observation></entry>"""


def test_reference_range_from_text():
    rr = """<referenceRange><observationRange>
      <text>3.4 -
        8.2 E9/l</text></observationRange></referenceRange>"""
    body = f"<component><section><code code='30954-2'/>{_lab_obs('5.1', rr)}</section></component>"
    labs = extract_lab_results(_root(body))
    assert len(labs) == 1
    assert labs[0].reference_range == "3.4 - 8.2 E9/l"


def test_reference_range_from_structured_value():
    rr = """<referenceRange><observationRange>
      <value xsi:type="IVL_PQ"><low value="3.4" unit="E9/l"/><high value="8.2" unit="E9/l"/></value>
    </observationRange></referenceRange>"""
    body = f"<component><section><code code='30954-2'/>{_lab_obs('5.1', rr)}</section></component>"
    assert extract_lab_results(_root(body))[0].reference_range == "3.4 - 8.2 E9/l"


def test_reference_range_from_narrative_reference():
    rr = """<referenceRange><observationRange>
      <text><reference value="#rr1"/></text></observationRange></referenceRange>"""
    narrative = "<text><table><tr><td ID='rr1'>3.4 - 8.2 E9/l</td></tr></table></text>"
    body = (
        f"<component><section><code code='30954-2'/>{narrative}{_lab_obs('5.1', rr)}"
        "</section></component>"
    )
    assert extract_lab_results(_root(body))[0].reference_range == "3.4 - 8.2 E9/l"


def test_reference_range_missing():
    body = f"<component><section><code code='30954-2'/>{_lab_obs('5.1', '')}</section></component>"
    assert extract_lab_results(_root(body))[0].reference_range is None


def _write(tmp_path: Path, xml: str) -> str:
    path = tmp_path / "DOC0001.XML"
    path.write_text(xml, encoding="utf-8")
    return str(path)


SERVICE_EVENT = """<documentationOf><serviceEvent classCode="PCPR">
  <effectiveTime><low value="{low}"/></effectiveTime>
</serviceEvent></documentationOf>"""


def test_summary_document_is_not_dated_at_birth(tmp_path):
    """A lifetime summary starts its service period at birthTime; that date must not be used."""
    xml = _doc(extra_header=SERVICE_EVENT.format(low="19500101"))
    summary = extract_document_summary(_write(tmp_path, xml))
    assert summary is not None
    assert summary.date == "2026-11-10T12:00:00"


def test_summary_birth_guard_handles_coarse_birth_time(tmp_path):
    """birthTime with year precision still matches a service start on that birth day."""
    xml = _doc(extra_header=SERVICE_EVENT.format(low="19500101"), birth="1950")
    summary = extract_document_summary(_write(tmp_path, xml))
    assert summary is not None
    assert summary.date == "2026-11-10T12:00:00"


@pytest.mark.parametrize(
    "effective_time",
    [
        '<effectiveTime><low value="20250505093000+0300"/></effectiveTime>',
        '<effectiveTime value="20250505093000+0300"/>',
    ],
)
def test_encounter_date_prefers_encompassing_encounter(tmp_path, effective_time):
    encounter = f"<componentOf><encompassingEncounter>{effective_time}</encompassingEncounter></componentOf>"
    # A different service-event date proves the encounter time is the one used
    xml = _doc(extra_header=SERVICE_EVENT.format(low="20240101080000+0200") + encounter)
    summary = extract_document_summary(_write(tmp_path, xml))
    assert summary is not None
    assert summary.date == "2025-05-05T09:30:00"


def test_service_event_date_used_when_not_birth(tmp_path):
    xml = _doc(extra_header=SERVICE_EVENT.format(low="20240615090000"))
    summary = extract_document_summary(_write(tmp_path, xml))
    assert summary is not None
    assert summary.date == "2024-06-15T09:00:00"


def test_process_files_splits_medications_and_skips_vaccines(tmp_path):
    entries = (
        _med_entry("Active drug", "55561003", high="20250101")
        + _med_entry("Stopped drug", "73425007")
        + _med_entry("Ended drug", None, high="20250101")
        + _med_entry("Ongoing drug", None, high="20270101")
    )
    body = MED_SECTION.format(entries=entries) + IMMUNIZATION_SECTION
    xml = _doc(body=body, extra_header=SERVICE_EVENT.format(low="19500101"))
    _write(tmp_path, xml)
    record = process_files(str(tmp_path), str(tmp_path / "out.json"), "DOC0001.XML")
    active = {m.name for m in record.clinical_summary.active_medications}
    history = {m.name for m in record.clinical_summary.medication_history}
    assert active == {"Active drug", "Ongoing drug"}
    assert history == {"Stopped drug", "Ended drug"}
    assert [i.vaccine_name for i in record.immunizations] == ["Test vaccine"]
    # The summary is dated by its own header date, not the birth date
    assert [e.date for e in record.encounters] == ["2026-11-10T12:00:00"]
