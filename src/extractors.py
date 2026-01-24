"""
Extraction logic for Maisa Parser.
Contains functions to parse specific sections of the CDA XML.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from lxml import etree

from .models import (
    Allergy,
    Diagnosis,
    DocumentSummary,
    Immunization,
    LabResult,
    Medication,
    PatientProfile,
    Procedure,
    SocialHistory,
)
from .utils import NS, parse_date

logger = logging.getLogger(__name__)


def extract_patient_profile(root: etree._Element) -> PatientProfile:
    """
    Extract patient demographic information from a CDA document.

    Args:
        root: The root element of the parsed CDA XML document.

    Returns:
        Dictionary containing patient demographics (name, DOB, gender,
        address, phone, email, national_id).
    """
    profile: dict[str, Any] = {}

    # Paths (relative to root, using namespace)
    patient_role = root.xpath("//v3:recordTarget/v3:patientRole", namespaces=NS)

    if not patient_role:
        return PatientProfile()

    pr = patient_role[0]

    # ID (National ID usually root="1.2.246.21" or similar, here we just take the first extension found or specific OID if known)
    # Based on DOC0001 example: <id root="1.2.840.114350.1.13.491.2.7.3.688884.100" extension="APOM49Z2MMLB7GM" />
    # We'll grab the extension of the first ID as a fallback 'national_id' or 'system_id'
    ids = pr.xpath("v3:id", namespaces=NS)
    profile["national_id"] = ids[0].get("extension") if ids else "Unknown"

    # Address
    addr = pr.xpath("v3:addr", namespaces=NS)
    address_parts = []
    if addr:
        for part in addr[0].iterchildren():
            if part.text:
                address_parts.append(part.text)
    profile["address"] = ", ".join(address_parts)

    # Telecom
    telecoms = pr.xpath("v3:telecom", namespaces=NS)
    profile["phone"] = next(
        (t.get("value") for t in telecoms if t.get("value", "").startswith("tel:")), ""
    ).replace("tel:", "")
    profile["email"] = next(
        (t.get("value") for t in telecoms if t.get("value", "").startswith("mailto:")),
        "",
    ).replace("mailto:", "")

    # Patient Entity
    patient = pr.xpath("v3:patient", namespaces=NS)
    if patient:
        p = patient[0]
        # Name
        # Prefer 'L' (Legal) otherwise first
        names = p.xpath('v3:name[@use="L"]', namespaces=NS)
        if not names:
            names = p.xpath("v3:name", namespaces=NS)

        if names:
            target_name = names[0]
            given = target_name.xpath("v3:given/text()", namespaces=NS)
            family = target_name.xpath("v3:family/text()", namespaces=NS)
            profile["full_name"] = f"{' '.join(given)} {' '.join(family)}".strip()
        else:
            profile["full_name"] = "Unknown"

        # Gender
        gender = p.xpath("v3:administrativeGenderCode", namespaces=NS)
        profile["gender"] = gender[0].get("displayName") if gender else "Unknown"

        # DOB
        birth_time = p.xpath("v3:birthTime", namespaces=NS)
        profile["dob"] = (
            parse_date(birth_time[0].get("value")) if birth_time else "Unknown"
        )

    return PatientProfile(**profile)


def extract_allergies(root: etree._Element) -> list[Allergy]:
    """
    Extract allergy information from a CDA document.

    Parses the Allergies section (LOINC code 48765-2) and handles
    negationInd for "No Known Allergies" cases.

    Args:
        root: The root element of the parsed CDA XML document.

    Returns:
        List of allergy dictionaries with 'substance' and 'status' keys.
    """
    allergies: list[Allergy] = []
    # 48765-2 is Allergies Document code
    section = root.xpath('//v3:section[v3:code[@code="48765-2"]]', namespaces=NS)
    if not section:
        return []

    # Inside section, look for observations
    entries = section[0].xpath(
        ".//v3:entry/v3:act/v3:entryRelationship/v3:observation", namespaces=NS
    )

    for obs in entries:
        # Check for negationInd (No known allergies)
        negation = obs.get("negationInd")

        # The observation code usually describes the allergy observation type (e.g. Allergy to substance)
        # The participant or value describes the substance.

        # In the provided XML (No known allergies):
        # <observation ... negationInd="true">
        #   <code code="419199007" ... displayName="Allergy to substance (disorder)" />
        #   <value nullFlavor="NA" ... />

        # If value is present (CD), it might be the substance.
        val_node = obs.xpath("v3:value", namespaces=NS)
        substance = "Unknown"

        if val_node:
            val = val_node[0]
            if val.get("displayName"):
                substance = val.get("displayName")
            elif val.get("code") and not val.get("nullFlavor"):
                substance = val.get("code")  # Or lookup

        # If substance is unknown and negation is true, it implies "No Allergy" equivalent
        if negation == "true":
            # Check code
            code_node = obs.xpath("v3:code", namespaces=NS)
            if code_node and code_node[0].get("code") == "419199007":
                # "Allergy to substance" negated -> No Known Allergies
                substance = "No Known Allergies"

        # Status
        status_node = obs.xpath("v3:statusCode", namespaces=NS)
        status = status_node[0].get("code") if status_node else "Unknown"

        if substance != "Unknown":
            allergies.append(Allergy(substance=substance, status=status))

    return allergies


def extract_medications(root: etree._Element) -> list[Medication]:
    """
    Extract medication information from a CDA document.

    Parses substanceAdministration elements to extract drug names,
    ATC codes, dosage instructions, and date ranges.

    Args:
        root: The root element of the parsed CDA XML document.

    Returns:
        List of medication dictionaries with name, ATC code, dosage,
        dates, and status.
    """
    meds: list[Medication] = []
    substances = root.xpath("//v3:substanceAdministration", namespaces=NS)

    for sub in substances:
        # Product
        man_mat = sub.xpath(
            ".//v3:manufacturedProduct/v3:manufacturedMaterial/v3:code", namespaces=NS
        )
        if not man_mat:
            continue

        drug_code_el = man_mat[0]

        # Name: prioritize originalText (reference) -> lookup in text, or translation displayName
        # The instructions say: "Extract Drug Name... Extract ATC code from translation tag"

        # ATC Code
        atc_node = drug_code_el.xpath(
            'v3:translation[@codeSystemName="WHO ATC"]', namespaces=NS
        )
        atc_code = atc_node[0].get("code") if atc_node else None

        # Name
        # Check originalText reference
        orig_text = drug_code_el.xpath("v3:originalText/v3:reference", namespaces=NS)
        name = "Unknown"
        if orig_text:
            ref_id = orig_text[0].get("value").replace("#", "")
            # Find in text
            text_node = root.xpath(
                f'//*[@ID="{ref_id}"]', namespaces=NS
            )  # ID is case sensitive usually, XML IDs are unique
            if text_node:
                name = "".join(text_node[0].itertext()).strip()

        if name == "Unknown" and drug_code_el.get("displayName"):
            name = drug_code_el.get("displayName")

        if name == "Unknown" and atc_node and atc_node[0].get("displayName"):
            name = atc_node[0].get("displayName")

        # Dosage
        # text reference
        text_ref_node = sub.xpath("v3:text/v3:reference", namespaces=NS)
        dosage = ""
        if text_ref_node:
            ref_id = text_ref_node[0].get("value").replace("#", "")
            text_node = root.xpath(f'//*[@ID="{ref_id}"]', namespaces=NS)
            if text_node:
                dosage = "".join(text_node[0].itertext()).strip()

        # Dates
        def_eff = sub.xpath("v3:effectiveTime", namespaces=NS)
        start_date = None
        end_date = None
        if def_eff:
            # Check if it has low/high
            low = def_eff[0].xpath("v3:low", namespaces=NS)
            high = def_eff[0].xpath("v3:high", namespaces=NS)
            if low:
                start_date = parse_date(low[0].get("value"))
            if high:
                end_date = parse_date(high[0].get("value"))

            # Sometimes it's a single value attribute
            if not low and not high and def_eff[0].get("value"):
                start_date = parse_date(def_eff[0].get("value"))

        # Status
        status_node = sub.xpath("v3:statusCode", namespaces=NS)
        status = status_node[0].get("code") if status_node else "Unknown"

        meds.append(
            Medication(
                name=name,
                atc_code=atc_code,
                dosage=dosage,
                start_date=start_date,
                end_date=end_date,
                status=status,
            )
        )

    return meds


def extract_lab_results(root: etree._Element) -> list[LabResult]:
    """
    Extract laboratory results and vitals from a CDA document.

    Parses observations with Physical Quantity (PQ) values to extract
    test names, numeric results, units, and interpretations.

    Args:
        root: The root element of the parsed CDA XML document.

    Returns:
        List of lab result dictionaries with test_name, result_value,
        unit, interpretation, and timestamp.
    """
    results: list[LabResult] = []

    # 30954-2 is 'Relevant diagnostic tests/laboratory data'
    # 8716-3 is 'Vital signs'
    # We scan all relevant observations.

    # Strategy: Find all observations that have a PQ value (Physical Quantity) or are within these sections.
    # Broad scan for observations with values.

    observations = root.xpath("//v3:observation", namespaces=NS)

    for obs in observations:
        # Must have a value
        val_node = obs.xpath("v3:value", namespaces=NS)
        if not val_node:
            continue

        val = val_node[0]

        # Check type
        # Labs usually PQ.
        # But some might be CO (Coded) or ST.
        # Strict prompt: "Iterate ... where value type is PQ"
        xsi_type = val.get("{http://www.w3.org/2001/XMLSchema-instance}type")
        if xsi_type != "PQ":
            continue

        # Extract fields
        code_node = obs.xpath("v3:code", namespaces=NS)
        test_name = code_node[0].get("displayName") if code_node else "Unknown"

        value = val.get("value")
        unit = val.get("unit")

        try:
            float_val = float(value)
        except (ValueError, TypeError):
            float_val = None

        # Interpretation
        interp_node = obs.xpath("v3:interpretationCode", namespaces=NS)
        interp_code = interp_node[0].get("code") if interp_node else None

        map_interp = {"H": "High", "L": "Low", "A": "Abnormal", "N": "Normal"}
        interpretation = (
            map_interp.get(str(interp_code), interp_code) if interp_code else None
        )

        # Timestamp
        eff_time = obs.xpath("v3:effectiveTime", namespaces=NS)
        timestamp = parse_date(eff_time[0].get("value")) if eff_time else None

        results.append(
            LabResult(
                timestamp=timestamp,
                test_name=test_name,
                result_value=float_val,
                unit=unit,
                interpretation=interpretation,
                reference_range=None,
            )
        )

    return results


def extract_diagnoses(root: etree._Element) -> list[Diagnosis]:
    """
    Extract diagnoses from a CDA document.

    Parses the Problem List section (LOINC 11450-4) to find diagnoses.
    The actual diagnosis is nested inside act/entryRelationship/observation/value.

    Args:
        root: The root element of the parsed CDA XML document.

    Returns:
        List of diagnosis dictionaries with code, display_name, status, and onset_date.
    """
    diagnoses: list[Diagnosis] = []

    # Primary: Problem List section (11450-4)
    section = root.xpath('//v3:section[v3:code[@code="11450-4"]]', namespaces=NS)

    if section:
        # Look for entries containing act (Concern wrapper) -> observation (Problem)
        entries = section[0].xpath(".//v3:entry/v3:act", namespaces=NS)

        for act in entries:
            # Get status from the act (concern status)
            status_node = act.xpath("v3:statusCode", namespaces=NS)
            status = status_node[0].get("code") if status_node else "unknown"

            # The actual diagnosis is in entryRelationship/observation/value
            observations = act.xpath(
                "v3:entryRelationship/v3:observation", namespaces=NS
            )

            for obs in observations:
                # Value contains the coded diagnosis (CD type)
                vals = obs.xpath('v3:value[@xsi:type="CD"]', namespaces=NS)
                for v in vals:
                    code = v.get("code")
                    code_system = v.get("codeSystemName") or ""

                    # Accept ICD-10, SNOMED CT, or other diagnostic codes
                    if code and (
                        "ICD" in code_system or "SNOMED" in code_system or code
                    ):
                        display_name = v.get("displayName")

                        # Try to get name from originalText reference if not in displayName
                        if not display_name:
                            orig_ref = v.xpath(
                                "v3:originalText/v3:reference/@value", namespaces=NS
                            )
                            if orig_ref:
                                ref_id = orig_ref[0].replace("#", "")
                                text_node = root.xpath(
                                    f'//*[@ID="{ref_id}"]', namespaces=NS
                                )
                                if text_node:
                                    display_name = "".join(
                                        text_node[0].itertext()
                                    ).strip()

                        # Get onset date if available
                        onset_date = None
                        eff_time = obs.xpath("v3:effectiveTime/v3:low", namespaces=NS)
                        if eff_time:
                            onset_date = parse_date(eff_time[0].get("value"))

                        diagnoses.append(
                            Diagnosis(
                                code=code,
                                code_system=code_system,
                                display_name=display_name or code or "Unknown",
                                status=status,
                                onset_date=onset_date,
                            )
                        )

    # Fallback: Also check for diagnoses in other sections (legacy approach)
    if not diagnoses:
        acts = root.xpath(
            '//v3:act[@classCode="ACT"][v3:statusCode[@code="active"]]', namespaces=NS
        )
        for act in acts:
            obs_list = act.xpath(
                ".//v3:entryRelationship/v3:observation", namespaces=NS
            )
            for obs in obs_list:
                vals = obs.xpath('v3:value[@xsi:type="CD"]', namespaces=NS)
                for v in vals:
                    code_sys = v.get("codeSystemName") or ""
                    if "ICD" in code_sys:
                        diagnoses.append(
                            Diagnosis(
                                code=v.get("code"),
                                code_system=code_sys,
                                display_name=v.get("displayName")
                                or v.get("code")
                                or "Unknown",
                                status="active",
                                onset_date=None,
                            )
                        )

    return diagnoses


def extract_procedures(root: etree._Element) -> list[Procedure]:
    """
    Extract procedures from a CDA document.

    Parses the Procedures section (LOINC 47519-4) to find medical procedures.

    Args:
        root: The root element of the parsed CDA XML document.

    Returns:
        List of procedure dictionaries with code, name, and date.
    """
    procedures: list[Procedure] = []

    # Procedures section (47519-4)
    section = root.xpath('//v3:section[v3:code[@code="47519-4"]]', namespaces=NS)

    if section:
        proc_entries = section[0].xpath(".//v3:entry/v3:procedure", namespaces=NS)

        for proc in proc_entries:
            code_node = proc.xpath("v3:code", namespaces=NS)
            if not code_node:
                continue

            code_el = code_node[0]
            code = code_el.get("code")
            code_system = code_el.get("codeSystemName") or ""
            display_name = code_el.get("displayName")

            # Try originalText if no displayName
            if not display_name:
                orig_text = code_el.xpath("v3:originalText", namespaces=NS)
                if orig_text:
                    ref = orig_text[0].xpath("v3:reference/@value", namespaces=NS)
                    if ref:
                        ref_id = ref[0].replace("#", "")
                        text_node = root.xpath(f'//*[@ID="{ref_id}"]', namespaces=NS)
                        if text_node:
                            display_name = "".join(text_node[0].itertext()).strip()
                    else:
                        display_name = "".join(orig_text[0].itertext()).strip()

            # Get procedure date
            proc_date = None
            eff_time = proc.xpath("v3:effectiveTime", namespaces=NS)
            if eff_time:
                # Could be single value or low/high
                if eff_time[0].get("value"):
                    proc_date = parse_date(eff_time[0].get("value"))
                else:
                    low = eff_time[0].xpath("v3:low", namespaces=NS)
                    if low:
                        proc_date = parse_date(low[0].get("value"))

            # Status
            status_node = proc.xpath("v3:statusCode", namespaces=NS)
            status = status_node[0].get("code") if status_node else "completed"

            if code:
                procedures.append(
                    Procedure(
                        code=code,
                        code_system=code_system,
                        name=display_name or code or "Unknown",
                        date=proc_date,
                        status=status,
                    )
                )

    return procedures


def extract_social_history(root: etree._Element) -> SocialHistory:
    """
    Extract social history from a CDA document.

    Parses the Social History section (LOINC 29762-2) for tobacco, alcohol use, etc.

    Args:
        root: The root element of the parsed CDA XML document.

    Returns:
        Dictionary with social history items (tobacco, alcohol, etc.).
    """
    social_history: dict[str, Any] = {}

    # Social History section (29762-2)
    section = root.xpath('//v3:section[v3:code[@code="29762-2"]]', namespaces=NS)

    if section:
        observations = section[0].xpath(".//v3:observation", namespaces=NS)

        for obs in observations:
            code_node = obs.xpath("v3:code", namespaces=NS)
            if not code_node:
                continue

            code = code_node[0].get("code")
            display_name = code_node[0].get("displayName") or ""

            # Get value
            value_node = obs.xpath("v3:value", namespaces=NS)
            value = None
            if value_node:
                val = value_node[0]
                value = val.get("displayName") or val.text or val.get("code")

            # Map common LOINC codes to readable keys
            # 72166-2 = Tobacco smoking status
            # 11367-0 = History of tobacco use
            # 11331-6 = History of alcohol use
            if code == "72166-2" or "tobacco" in display_name.lower():
                social_history["tobacco_smoking"] = value
            elif code == "11367-0" or "smokeless" in display_name.lower():
                social_history["smokeless_tobacco"] = value
            elif code == "11331-6" or "alcohol" in display_name.lower():
                social_history["alcohol"] = value
            else:
                # Generic entry
                key = display_name.lower().replace(" ", "_") if display_name else code
                social_history[key] = value

    return SocialHistory(**social_history)


def extract_immunizations(root: etree._Element) -> list[Immunization]:
    """
    Extract immunizations from a CDA document.

    Parses the Immunizations section (LOINC 11369-6).

    Args:
        root: The root element of the parsed CDA XML document.

    Returns:
        List of immunization dictionaries.
    """
    immunizations: list[Immunization] = []

    # Immunizations section (11369-6)
    section = root.xpath('//v3:section[v3:code[@code="11369-6"]]', namespaces=NS)

    if section:
        entries = section[0].xpath(
            ".//v3:entry/v3:substanceAdministration", namespaces=NS
        )

        for entry in entries:
            # Get vaccine info from manufacturedMaterial
            material = entry.xpath(
                ".//v3:manufacturedProduct/v3:manufacturedMaterial/v3:code",
                namespaces=NS,
            )

            vaccine_name = None
            vaccine_code = None

            if material:
                code_el = material[0]
                vaccine_code = code_el.get("code")
                vaccine_name = code_el.get("displayName")

                # Try translation for ATC code
                translation = code_el.xpath(
                    'v3:translation[@codeSystemName="WHO ATC"]', namespaces=NS
                )
                if translation:
                    vaccine_code = translation[0].get("code") or vaccine_code

                # Try originalText reference
                if not vaccine_name:
                    orig_ref = code_el.xpath(
                        "v3:originalText/v3:reference/@value", namespaces=NS
                    )
                    if orig_ref:
                        ref_id = orig_ref[0].replace("#", "")
                        text_node = root.xpath(f'//*[@ID="{ref_id}"]', namespaces=NS)
                        if text_node:
                            vaccine_name = "".join(text_node[0].itertext()).strip()

            # Get administration date
            admin_date = None
            eff_time = entry.xpath("v3:effectiveTime", namespaces=NS)
            if eff_time:
                if eff_time[0].get("value"):
                    admin_date = parse_date(eff_time[0].get("value"))
                else:
                    low = eff_time[0].xpath("v3:low", namespaces=NS)
                    if low:
                        admin_date = parse_date(low[0].get("value"))

            # Status
            status_node = entry.xpath("v3:statusCode", namespaces=NS)
            status = status_node[0].get("code") if status_node else "completed"

            if vaccine_name or vaccine_code:
                immunizations.append(
                    Immunization(
                        vaccine_name=vaccine_name or vaccine_code or "Unknown",
                        vaccine_code=vaccine_code,
                        date=admin_date,
                        status=status,
                    )
                )

    return immunizations


def extract_document_summary(file_path: str) -> DocumentSummary | None:
    """
    Extract document-level summary from a CDA file.

    Parses a single CDA XML file to extract encounter metadata including
    date, author/provider, document type, and narrative clinical notes.
    Filters out structured sections (medications, labs, etc.) to focus
    on free-text clinical notes.

    Args:
        file_path: Path to the CDA XML file.

    Returns:
        Dictionary with date, type, provider, notes, and source_file,
        or None if parsing fails.
    """
    try:
        tree = etree.parse(file_path)
        root = tree.getroot()

        # 1. Document Date (ServiceEvent effectiveTime low, or Header effectiveTime)
        doc_date = None
        service_event_time = root.xpath(
            "//v3:documentationOf/v3:serviceEvent/v3:effectiveTime/v3:low/@value",
            namespaces=NS,
        )
        if service_event_time:
            doc_date = parse_date(service_event_time[0])

        if not doc_date:
            eff_time = root.xpath("//v3:effectiveTime/@value", namespaces=NS)
            if eff_time:
                doc_date = parse_date(eff_time[0])

        # 2. Author / Provider
        author_name = "Unknown"
        assigned_author = root.xpath(
            "//v3:author/v3:assignedAuthor/v3:assignedPerson/v3:name", namespaces=NS
        )
        if assigned_author:
            # Join parts
            parts = [t for t in assigned_author[0].itertext() if t.strip()]
            author_name = " ".join(parts)
        elif root.xpath(
            "//v3:author/v3:assignedAuthor/v3:representedOrganization/v3:name",
            namespaces=NS,
        ):
            author_name = root.xpath(
                "//v3:author/v3:assignedAuthor/v3:representedOrganization/v3:name",
                namespaces=NS,
            )[0].text

        # 3. Title / Type
        title = "Clinical Document"
        title_node = root.xpath("//v3:title", namespaces=NS)
        if title_node and title_node[0].text:
            title = title_node[0].text

        # 4. Narrative Content (Body Text)
        # Strategy: Extract text from sections.
        # Prefer sections that are NOT purely structured lists (Medications, Labs, Allergies) if possible,
        # OR just dump everything readable.
        # User requested: "Extract the Body Text (component/structuredBody//text)"
        # We will iterate sections and act intelligently.

        narrative_parts = []
        body = root.xpath("//v3:component/v3:structuredBody", namespaces=NS)
        if body:
            sections = body[0].xpath(".//v3:section", namespaces=NS)
            for section in sections:
                sect_title = section.xpath("v3:title/text()", namespaces=NS)
                sect_title_str = sect_title[0] if sect_title else ""

                # Filter out noisy list sections
                EXCLUDED_SECTIONS = [
                    # Finnish sections
                    "Lääkkeet",
                    "Tulokset",
                    "Rokotukset",
                    "Allergiat",
                    "Aktiiviset tarpeet/diagnoosit",
                    "Viimeisimmät tallennetut peruselintoiminnot",
                    "Hoito-ohjelma",
                    "Käyntisyyt",
                    "Palvelukontaktit",
                    "Annetut lääkkeet",
                    "Toimenpiteet",
                    "Omatiimit",
                    "Merkintä kohteesta Apotti",
                    "Määrätyt reseptit",
                    "Elintapahistoria",
                    # English equivalents (for safety/compatibility)
                    "Medications",
                    "Results",
                    "Immunizations",
                    "Allergies",
                    "Problem List",  # or "Active Problems"
                    "Vitals",
                    "Care Plan",
                    "Encounters",  # or "Reason for Visit"
                    "Procedures",
                    "Care Teams",
                ]

                # Check if title matches exclusion list (partial match or exact?)
                # User titles seem to vary slightly, but start with these keywords.
                skip = False
                for excluded in EXCLUDED_SECTIONS:
                    if excluded in sect_title_str:
                        skip = True
                        break

                if skip:
                    continue

                # Retrieve text block
                text_node = section.xpath("v3:text", namespaces=NS)
                if text_node:
                    # Extract all text recursively from this node
                    # Use itertext() to get clean text
                    raw_text = "".join(text_node[0].itertext())
                    clean_text = " ".join(raw_text.split())  # Collapse whitespace

                    if clean_text:
                        narrative_parts.append(f"{sect_title_str}: {clean_text}")

        notes = "\n".join(narrative_parts)

        return DocumentSummary(
            date=doc_date,
            type=title,
            provider=author_name,
            notes=notes,
            source_file=os.path.basename(file_path),
        )

    except etree.XMLSyntaxError as e:
        logger.warning("XML syntax error in %s: %s", file_path, e)
        return None
    except Exception as e:
        logger.warning("Error extracting summary from %s: %s", file_path, e)
        return None
