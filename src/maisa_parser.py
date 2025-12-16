import os
import json
import datetime
import argparse
from lxml import etree

# Namespaces
NS = {
    "v3": "urn:hl7-org:v3",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


def parse_date(date_str):
    """Parses HL7 date string (YYYYMMDDHHMMSS+ZZZZ) to ISO 8601 (YYYY-MM-DDTHH:mm:ss)."""
    if not date_str:
        return None
    try:
        # Basic cleaning of the string
        cleaned_date = date_str.split("+")[
            0
        ]  # Remove timezone for simplicity if present, or handle it

        # Handle different precisions
        if len(cleaned_date) >= 14:
            dt = datetime.datetime.strptime(cleaned_date[:14], "%Y%m%d%H%M%S")
        elif len(cleaned_date) == 8:
            dt = datetime.datetime.strptime(cleaned_date, "%Y%m%d")
        else:
            # Fallback or partial date handling
            return date_str

        return dt.isoformat()
    except ValueError:
        return date_str


def extract_patient_profile(root):
    """Extracts patient demographic information."""
    profile = {}

    # Paths (relative to root, using namespace)
    patient_role = root.xpath("//v3:recordTarget/v3:patientRole", namespaces=NS)

    if not patient_role:
        return {}

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

    return profile


def extract_allergies(root):
    """Extracts allergies."""
    allergies = []
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
            allergies.append({"substance": substance, "status": status})

    return allergies


def extract_medications(root):
    """Extracts medications."""
    meds = []
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
            {
                "name": name,
                "atc_code": atc_code,
                "dosage": dosage,
                "start_date": start_date,
                "end_date": end_date,
                "status": status,
                "_raw_eff_high": end_date,  # Helper for sorting
            }
        )

    return meds


def extract_lab_results(root):
    """Extracts labs and vitals (mapped to schema lab_results)."""
    results = []

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
        interpretation = map_interp.get(interp_code, interp_code)

        # Timestamp
        eff_time = obs.xpath("v3:effectiveTime", namespaces=NS)
        timestamp = parse_date(eff_time[0].get("value")) if eff_time else None

        results.append(
            {
                "timestamp": timestamp,
                "test_name": test_name,
                "result_value": float_val,
                "unit": unit,
                "interpretation": interpretation,
                "reference_range": None,  # Complex to extract from range nodes usually, ignoring for now or todo
            }
        )

    return results


def extract_diagnoses(root):
    """Extracts diagnoses."""
    # Look for Act, classCode=ACT, statusCode=active
    # In 'Problem list' 11450-4

    diagnoses = []
    acts = root.xpath(
        '//v3:act[@classCode="ACT"][v3:statusCode[@code="active"]]', namespaces=NS
    )

    for act in acts:
        # Look for observation inside with ICD-10
        obs = act.xpath(".//v3:observation", namespaces=NS)
        for o in obs:
            # Value should be CD (Coded Descriptor)
            vals = o.xpath('v3:value[@xsi:type="CD"]', namespaces=NS)
            for v in vals:
                code_sys = v.get("codeSystemName")
                if code_sys and "ICD-10" in code_sys:
                    # Found one
                    diagnoses.append(
                        {
                            "code": v.get("code"),
                            "name": v.get("displayName")
                            or v.xpath(
                                "v3:originalText/v3:reference/@value", namespaces=NS
                            ),  # Tricky if reference
                        }
                    )
                    # Reference handling for name similar to Meds if needed.

    return diagnoses


def extract_document_summary(file_path):
    """Extracts document-level summary (Date, Author, Title, Narrative) from a CDA file."""
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

        return {
            "date": doc_date,
            "type": title,
            "provider": author_name,
            "notes": notes,
            "source_file": os.path.basename(file_path),
        }

    except Exception as e:
        print(f"Error extracting summary from {file_path}: {e}")
        return None


def process_files(data_dir, output_file, summary_file):
    """Processes generic CDA XML files."""
    files = [f for f in os.listdir(data_dir) if f.upper().endswith(".XML")]
    files.sort()

    combined_data = {
        "patient_profile": {},
        "clinical_summary": {
            "allergies": [],
            "active_medications": [],
            "medication_history": [],
        },
        "lab_results": [],
        "encounters": [],
        "diagnoses": [],
    }

    # Process Summary File (defaults to DOC0001.XML) specifically for the "Dashboard" data
    doc0001_path = os.path.join(data_dir, summary_file)
    if os.path.exists(doc0001_path):
        print(f"Processing Summary {doc0001_path}...")
        try:
            tree = etree.parse(doc0001_path)
            root = tree.getroot()

            combined_data["patient_profile"] = extract_patient_profile(root)
            combined_data["clinical_summary"]["allergies"] = extract_allergies(root)

            meds = extract_medications(root)
            # Separate active vs history (simple logic based on status or date)
            # Schema expects separation
            for m in meds:
                if m["status"] == "active" or (m["end_date"] is None):
                    combined_data["clinical_summary"]["active_medications"].append(m)
                else:
                    combined_data["clinical_summary"]["medication_history"].append(m)

            combined_data["lab_results"] = extract_lab_results(root)
            combined_data["diagnoses"] = extract_diagnoses(root)

        except Exception as e:
            print(f"Failed to process summary file {doc0001_path}: {e}")

    # Now iterate ALL files (including DOC0001 if desired, but primarily others) for Encounters/Notes
    print("Processing all files for Encounters/Notes...")
    all_encounters = []

    for f in files:
        f_path = os.path.join(data_dir, f)
        doc_summary = extract_document_summary(f_path)
        if doc_summary:
            all_encounters.append(doc_summary)

    # Sort encounters by date
    all_encounters.sort(
        key=lambda x: x["date"] if x["date"] else "1900-01-01", reverse=True
    )
    combined_data["encounters"] = all_encounters

    # Write output
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(combined_data, f, indent=2, ensure_ascii=False)
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
