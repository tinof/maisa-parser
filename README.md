# Maisa Clinical Data Parser

[![CI](https://github.com/tinof/maisa-parser/actions/workflows/ci.yml/badge.svg)](https://github.com/tinof/maisa-parser/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> [!NOTE]
> **Suomenkielinen ohjeistus**: [Lue ohjeet suomeksi tästä](README_fi.md)

A Python tool to parse and consolidate HL7 CDA (Clinical Document Architecture) XML files exported from the **Maisa** patient portal (used by **Apotti** in Finland).

It extracts key health information into a structured, machine-readable JSON format (`patient_history.json`).

## Features

- **Consolidated Patient History**: Merges data from multiple `DOC*.XML` files into a single chronological timeline.
- **Narrative Extraction**: Intelligently extracts free-text clinical notes ("Päivittäismerkinnät", "Hoidon tarpeen arviointi") while filtering out redundant structured lists (medications, labs) to reduce noise.
- **Structured Data Parsing**:
  - **Patient Profile**: Demographics, contact info.
  - **Medications**: Active list and history with dates and dosage.
  - **Lab Results**: Test names, values, units, and timestamps.
  - **Diagnoses**: Active problems with ICD-10/SNOMED codes (from Problem List section).
  - **Procedures**: Medical procedures with Finnish national codes (lumbar puncture, ENMG, OCT, etc.).
  - **Immunizations**: Vaccination records with ATC codes and dates.
  - **Social History**: Tobacco use, alcohol consumption status.
  - **Allergies**: Status and substances.
- **Deduplication**: Handles duplicate entries across multiple documents.
- **Clean Output**: Produces a clean `patient_history.json` file.
- **Medical Data Safety**: Uses **Pydantic** models to strictly validate all parsed data. If the XML data doesn't match the expected schema, the parser catches it immediately rather than producing corrupt output.

## Safety & Quality Assurance

This project adheres to professional software standards suitable for handling health data:

- **Type Safety**: Fully typed codebase checked with `basedpyright`.
- **Validation**: strict data models via `Pydantic` ensure integrity.
- **Security**: Automated security scanning using `bandit` to detect vulnerabilities.
- **CI/CD**: Automated testing pipeline ensures the parser is reliable across Python versions.

## Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) (recommended) or `pip`

## Installation

### Recommended: uv (isolated installation)

```bash
uv tool install git+https://github.com/tinof/maisa-parser.git
```

This installs `maisa-parser` as a global command in an isolated environment.

### One-liner trial (no install)

```bash
uvx --from git+https://github.com/tinof/maisa-parser.git maisa-parser --help
```

### Alternative: pip

```bash
pip install git+https://github.com/tinof/maisa-parser.git
```

### Development installation

```bash
git clone https://github.com/tinof/maisa-parser.git
cd maisa-parser
uv sync --all-extras
```

## Usage

1. **Export Data**: Download your health data dump from Maisa ("Tilanneyhteenveto" or similar export). After extracting the ZIP file, you'll see a folder structure like this:

    ```
    Tilanneyhteenveto_DD_Month_YYYY/
    ├── HTML/
    │   ├── IMAGES/
    │   └── STYLE/
    ├── IHE_XDM/
    │   └── <PatientFolder>/     ← This folder contains the XML files!
    │       ├── DOC0001.XML
    │       ├── DOC0002.XML
    │       ├── ...
    │       ├── METADATA.XML
    │       └── STYLE.XSL
    ├── INDEX.HTM
    └── README - Open for Instructions.TXT
    ```

    > [!IMPORTANT]
    > Point the parser to the **`IHE_XDM/<PatientFolder>/`** directory that contains the `DOC*.XML` files, **not** the root extracted folder.

2. **Run the parser**:

    ```bash
    # Run with default settings (redacted privacy)
    maisa-parser /path/to/IHE_XDM/<PatientFolder>/
    ```

    For example:

    ```bash
    maisa-parser ~/Downloads/Tilanneyhteenveto_16_joulu_2025/IHE_XDM/Ilias1/
    ```

3. **View Output**: The script generates a `patient_history.json` file in your current working directory.

## Privacy & Data Safety

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

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Unknown error |
| 2 | Invalid arguments / input path not found |
| 3 | XML parse error |
| 4 | Data extraction error |
| 5 | Output write error |

## Output Structure

The generated JSON contains:

```json
{
  "patient_profile": {
    "full_name": "...",
    "dob": "1990-01-15T00:00:00",
    "gender": "...",
    "address": "...",
    "phone": "...",
    "email": "..."
  },
  "clinical_summary": {
    "allergies": [ ... ],
    "active_medications": [ ... ],
    "medication_history": [ ... ]
  },
  "diagnoses": [
    { "code": "J45", "code_system": "ICD10", "display_name": "Asthma", "status": "active" }
  ],
  "procedures": [
    { "code": "WX110", "name": "Blood pressure measurement", "date": "2023-05-10T00:00:00" }
  ],
  "immunizations": [
    { "vaccine_name": "Influenza vaccine", "vaccine_code": "J07BB02", "date": "2023-10-15T00:00:00" }
  ],
  "social_history": {
    "tobacco_smoking": "Never smoked",
    "alcohol": "Non-drinker"
  },
  "lab_results": [ ... ],
  "encounters": [
    {
      "date": "2024-10-10T12:00:00",
      "type": "Hoito- ja palveluyhteenveto",
      "provider": "Dr. Name",
      "notes": "Narrative text of the visit...",
      "source_file": "DOC0018.XML"
    }
  ]
}
```

## ⚠️ Important Note on Privacy

This tool processes **sensitive personal health information**.

- **Do not commit** your XML data files or the generated JSON output to GitHub or any public repository.
- A `.gitignore` file is included to help prevent accidental commits of `.XML` and `.json` files.
- Always handle your medical data with care.

## How to export your data from Maisa

1. Log in to **[Maisa.fi](https://www.maisa.fi)**.
2. Go to **Menu** > **Sharing** > **Download My Record** (Lataa tietoni).
3. Select **"Lucy XML"** (or "Everything").
4. Download the ZIP file and unzip it.
5. You will see a folder `IHE_XDM` containing the `DOC*.XML` files. This is the folder you process.

## ⚠️ Legal & Liability Disclaimer

**Disclaimer:** This software is for **educational and informational purposes only**. It is **not** a medical device and should not be used for diagnosis or treatment. Always consult a professional for medical advice. The authors are not responsible for any errors in parsing or data representation.

By using this tool, you agree that you are solely responsible for safeguarding your own medical data.

## Contributing

Feel free to submit issues or pull requests if you find bugs or want to improve the parsing logic for different types of Maisa documents.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
