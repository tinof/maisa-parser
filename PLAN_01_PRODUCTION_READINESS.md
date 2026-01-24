# Plan 01: Production Readiness

> **Prerequisite for**: [PLAN_02_PRIVACY_UPGRADE.md](./PLAN_02_PRIVACY_UPGRADE.md)  
> **Goal**: Make the parser installable, observable, and reliable  
> **Estimated effort**: 2-3 hours

---

## Executive Summary

This plan fixes foundational issues that block production use:
1. **Broken execution** - Can't run via documented command
2. **No observability** - Uses `print()`, no structured logging
3. **Silent failures** - Errors swallowed, no exit codes
4. **Unpinned dependencies** - Non-reproducible builds

---

## Task 1: Fix CLI Entry Point

### Problem
README says `python src/maisa_parser.py /path/to/data` but this fails with `ImportError` due to relative imports.

### Solution
Add proper entry point in `pyproject.toml`:

```toml
[project.scripts]
maisa-parser = "src.maisa_parser:main"
```

### Implementation
1. Update `pyproject.toml` to add `[project.scripts]` section
2. Ensure `src/maisa_parser.py` has a `main()` function (wrap current `if __name__ == "__main__"` block)
3. Update README to show: `maisa-parser /path/to/data` (after pip install)
4. Keep fallback instruction: `python -m src.maisa_parser /path/to/data`

### Acceptance Criteria
- [ ] `pip install -e .` works
- [ ] `maisa-parser --help` works
- [ ] `maisa-parser /path/to/data` produces output

---

## Task 2: Migrate to Structured Logging

### Problem
All output uses `print()` - no log levels, no structured output, can't integrate with pipelines.

### Solution
Replace all `print()` calls with Python `logging` module.

### Implementation

**A. Create logging configuration in `src/maisa_parser.py`:**

```python
import logging

def setup_logging(verbosity: int = 0, json_format: bool = False) -> None:
    """Configure logging based on verbosity level.
    
    Args:
        verbosity: 0=WARNING, 1=INFO, 2=DEBUG
        json_format: If True, output JSON lines for pipeline consumption
    """
    level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}.get(verbosity, logging.DEBUG)
    
    if json_format:
        format_str = '{"time":"%(asctime)s","level":"%(levelname)s","module":"%(module)s","message":"%(message)s"}'
    else:
        format_str = "%(levelname)s: %(message)s"
    
    logging.basicConfig(level=level, format=format_str)

logger = logging.getLogger(__name__)
```

**B. Add CLI flags:**

```python
parser.add_argument("-v", "--verbose", action="count", default=0,
                    help="Increase verbosity (-v=INFO, -vv=DEBUG)")
parser.add_argument("--log-format", choices=["text", "json"], default="text",
                    help="Log output format")
parser.add_argument("-q", "--quiet", action="store_true",
                    help="Suppress all output except errors")
```

**C. Replace all print statements:**

| Current | Replace With |
|---------|--------------|
| `print(f"Processing {file}...")` | `logger.info("Processing %s", file)` |
| `print(f"Error: {e}")` | `logger.error("Failed to parse: %s", e)` |
| `print(f"Found {n} medications")` | `logger.debug("Extracted %d medications", n)` |
| `print(f"Output written to {path}")` | `logger.info("Output written to %s", path)` |

### Files to Update
- `src/maisa_parser.py` - All print statements
- `src/extractors.py` - Any print statements in extraction functions

### Acceptance Criteria
- [ ] No `print()` calls remain in `src/` (except intentional user output)
- [ ] `maisa-parser -v /path` shows INFO messages
- [ ] `maisa-parser -vv /path` shows DEBUG messages
- [ ] `maisa-parser -q /path` shows only errors
- [ ] `maisa-parser --log-format json /path` outputs JSON lines

---

## Task 3: Define Exit Codes and Error Handling

### Problem
Errors are printed and execution continues - no way to detect failures in scripts/pipelines.

### Solution
Define explicit exit codes and create custom exception hierarchy.

### Implementation

**A. Create `src/exceptions.py`:**

```python
"""Custom exceptions for Maisa Parser."""

class MaisaParserError(Exception):
    """Base exception for all parser errors."""
    exit_code: int = 1

class InputError(MaisaParserError):
    """Invalid input arguments or missing files."""
    exit_code: int = 2

class XMLParseError(MaisaParserError):
    """Failed to parse XML file."""
    exit_code: int = 3
    
    def __init__(self, message: str, filename: str | None = None):
        self.filename = filename
        super().__init__(f"{filename}: {message}" if filename else message)

class ExtractionError(MaisaParserError):
    """Failed to extract data from valid XML."""
    exit_code: int = 4
    
    def __init__(self, message: str, section: str | None = None):
        self.section = section
        super().__init__(f"[{section}] {message}" if section else message)

class OutputError(MaisaParserError):
    """Failed to write output file."""
    exit_code: int = 5
```

**B. Exit code contract (document in README):**

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Unknown error |
| 2 | Invalid arguments / input path not found |
| 3 | XML parse error |
| 4 | Data extraction error |
| 5 | Output write error |

**C. Update main() with proper error handling:**

```python
def main() -> int:
    """Main entry point. Returns exit code."""
    try:
        args = parse_args()
        setup_logging(args.verbose, args.log_format == "json")
        
        # ... processing logic ...
        
        return 0
    except InputError as e:
        logger.error("Input error: %s", e)
        return e.exit_code
    except XMLParseError as e:
        logger.error("Parse error: %s", e)
        return e.exit_code
    except ExtractionError as e:
        logger.error("Extraction error: %s", e)
        return e.exit_code
    except OutputError as e:
        logger.error("Output error: %s", e)
        return e.exit_code
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

**D. Add --fail-fast vs --continue-on-error:**

```python
parser.add_argument("--fail-fast", action="store_true",
                    help="Stop on first error (default: continue and report)")
```

### Acceptance Criteria
- [ ] `maisa-parser /nonexistent` exits with code 2
- [ ] `maisa-parser /path/with/bad.xml` exits with code 3 (or continues based on flag)
- [ ] Exit codes are documented in README
- [ ] `echo $?` after command shows correct code

---

## Task 4: Pin Dependencies

### Problem
`requirements.txt` uses `>=` version specifiers - builds are not reproducible.

### Solution
Use `uv` for dependency management with lockfile.

### Implementation

**A. Update `pyproject.toml` dependencies:**

```toml
[project]
dependencies = [
    "lxml>=4.9.0,<6.0.0",
    "pydantic>=2.0.0,<3.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "mypy>=1.0.0",
    "ruff>=0.1.0",
    "bandit>=1.7.0",
]
```

**B. Generate lockfile:**

```bash
uv pip compile pyproject.toml -o requirements.lock
uv pip compile pyproject.toml --extra dev -o requirements-dev.lock
```

**C. Update installation instructions in README:**

```markdown
## Installation

### Using uv (recommended)
```bash
uv pip install -e .
```

### Using pip
```bash
pip install -e .
```
```

### Acceptance Criteria
- [ ] `requirements.lock` exists with pinned versions
- [ ] `uv pip sync requirements.lock` produces identical environment
- [ ] CI uses lockfile for reproducible builds

---

## Task 5: Add CLI and Integration Tests

### Problem
Only extraction functions are tested. CLI, file discovery, and error paths are untested.

### Solution
Add end-to-end CLI tests and error case tests.

### Implementation

**A. Create `tests/test_cli.py`:**

```python
"""CLI integration tests."""
import subprocess
import pytest
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"

def test_cli_help():
    """Verify --help works."""
    result = subprocess.run(
        ["python", "-m", "src.maisa_parser", "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()

def test_cli_version():
    """Verify --version works."""
    result = subprocess.run(
        ["python", "-m", "src.maisa_parser", "--version"],
        capture_output=True, text=True
    )
    assert result.returncode == 0

def test_cli_missing_path():
    """Verify proper exit code for missing path."""
    result = subprocess.run(
        ["python", "-m", "src.maisa_parser", "/nonexistent/path"],
        capture_output=True, text=True
    )
    assert result.returncode == 2  # InputError

def test_cli_success(tmp_path):
    """Verify successful parse with fixtures."""
    output = tmp_path / "output.json"
    result = subprocess.run(
        ["python", "-m", "src.maisa_parser", str(FIXTURE_DIR), "-o", str(output)],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert output.exists()
```

**B. Create `tests/test_error_handling.py`:**

```python
"""Error handling tests."""
import pytest
from src.exceptions import XMLParseError, ExtractionError

def test_malformed_xml():
    """Verify XMLParseError for malformed input."""
    # Create malformed XML fixture and verify behavior

def test_missing_required_section():
    """Verify graceful handling of missing sections."""
    # Test with XML missing patient section
```

### Acceptance Criteria
- [ ] `pytest tests/test_cli.py` passes
- [ ] CLI tests cover: --help, --version, missing path, success path
- [ ] Error tests cover: malformed XML, missing sections

---

## Task 6: Output Schema Versioning

### Problem
JSON output structure is undocumented. Breaking changes would silently affect consumers.

### Solution
Add schema version to output and document structure.

### Implementation

**A. Update output structure:**

```python
# In maisa_parser.py, wrap output:
output = {
    "_schema_version": "1.0.0",
    "_generated_at": datetime.utcnow().isoformat() + "Z",
    "_generator": f"maisa-parser/{__version__}",
    "health_record": health_record.model_dump()
}
```

**B. Create `schemas/health_record.v1.schema.json`:**

Generate JSON Schema from Pydantic models for documentation:

```python
# scripts/generate_schema.py
from src.models import HealthRecord
import json

schema = HealthRecord.model_json_schema()
print(json.dumps(schema, indent=2))
```

### Acceptance Criteria
- [ ] Output JSON includes `_schema_version` field
- [ ] JSON Schema file exists in `schemas/`
- [ ] README documents output structure

---

## Implementation Order

| # | Task | Dependencies | Effort |
|---|------|--------------|--------|
| 1 | Fix CLI entry point | None | 15 min |
| 2 | Create exceptions.py | None | 10 min |
| 3 | Migrate to logging | Task 1 | 30 min |
| 4 | Add error handling to main() | Tasks 2, 3 | 20 min |
| 5 | Pin dependencies | None | 10 min |
| 6 | Add CLI tests | Tasks 1-4 | 30 min |
| 7 | Add schema versioning | None | 15 min |
| 8 | Update README | All above | 15 min |

---

## Verification Checklist

After implementation, verify:

```bash
# Installation
pip install -e .
maisa-parser --version
maisa-parser --help

# Logging
maisa-parser -v tests/fixtures/    # INFO level
maisa-parser -vv tests/fixtures/   # DEBUG level  
maisa-parser -q tests/fixtures/    # Quiet mode

# Exit codes
maisa-parser /nonexistent; echo "Exit: $?"  # Should be 2

# Tests
pytest tests/ -v

# Linting
ruff check src/
mypy src/
```

---

## Next Steps

After completing this plan, proceed to:
→ [PLAN_02_PRIVACY_UPGRADE.md](./PLAN_02_PRIVACY_UPGRADE.md)
