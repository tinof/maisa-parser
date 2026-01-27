# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Maisa Parser is a Python tool that parses HL7 CDA (Clinical Document Architecture) XML files exported from the Maisa patient portal (used by Apotti in Finland). It consolidates multiple XML documents into a single structured JSON file (`patient_history.json`).

## Commands

**STRICTLY use `uv` for all Python operations.**

| Command | Description |
|---------|-------------|
| `make install` | Install all dependencies including dev extras |
| `make fmt` | Format code with ruff |
| `make check` | Run linting + type checking |
| `make test` | Run pytest |
| `make upgrade` | Upgrade all dependencies to latest |
| `make build` | Build package |
| `make clean` | Clean build artifacts |
| `make` | Run install, check, and test |

### Direct commands (if needed)
```bash
uv sync --all-extras          # Install dependencies
uv run ruff check --fix       # Fix lint issues
uv run ruff format            # Format code
uv run basedpyright           # Type check
uv run pytest                 # Run tests
```

### Run the parser
```bash
# Parse XML files from a specific directory
uv run maisa-parser /path/to/IHE_XDM/<PatientFolder>/

# With custom output file
uv run maisa-parser /path/to/data -o output.json

# Specify different summary file (default: DOC0001.XML)
uv run maisa-parser /path/to/data --summary-file SUMMARY.XML
```

## Project Structure

```
src/
├── maisa_parser.py      # Main CLI and parsing logic
├── extractors.py        # Data extraction functions
├── models.py            # Pydantic models
├── exceptions.py        # Custom exceptions
├── privacy.py           # Privacy/anonymization utilities
├── utils.py             # Helper functions
└── __init__.py
tests/
├── test_cli.py          # CLI tests
├── test_privacy.py      # Privacy module tests
├── run_tests.py         # Test runner
├── fixtures/            # Sample XML files
└── __init__.py
```

## Code Style

- **Python**: 3.12+
- **Line length**: 100 characters
- **Formatter/Linter**: ruff
- **Type checker**: basedpyright
- **Quotes**: Double quotes
- **Imports**: Sorted with isort (via ruff)

## Architecture

### Core Parser (`src/maisa_parser.py`)

Single-module parser using `lxml` for XML processing with HL7 v3 namespace handling.

**Key extraction functions:**
- `extract_patient_profile()` - Demographics from `recordTarget/patientRole`
- `extract_allergies()` - From section code `48765-2`, handles negationInd for "No Known Allergies"
- `extract_medications()` - From `substanceAdministration`, extracts ATC codes from translation tags
- `extract_lab_results()` - Observations with `xsi:type="PQ"` (Physical Quantity)
- `extract_diagnoses()` - Active ACT elements with ICD-10 coded values
- `extract_document_summary()` - Document-level metadata and narrative text (filters excluded sections)

**Processing flow:**
1. DOC0001.XML (or specified summary file) provides structured clinical data (patient profile, allergies, medications, labs, diagnoses)
2. All DOC*.XML files are scanned for encounters/narrative notes
3. Results merged into single JSON output

### XML Namespace

All XPath queries use the HL7 v3 namespace:
```python
NS = {"v3": "urn:hl7-org:v3", "xsi": "http://www.w3.org/2001/XMLSchema-instance"}
```

### Test Fixtures

`tests/fixtures/` contains sample XML files (DOC0001.XML, DOC0002.XML, METADATA.XML) for testing. Tests verify extraction of patient name, medications, lab results, and encounter notes.

## Data Privacy

This tool processes sensitive health information. The `.gitignore` excludes `*.XML` and `*.json` files. Never commit patient data.
