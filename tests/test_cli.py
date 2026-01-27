"""CLI integration tests."""

import subprocess
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_cli_help():
    """Verify --help works."""
    result = subprocess.run(
        ["python", "-m", "src.maisa_parser", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()


def test_cli_version():
    """Verify --version works."""
    result = subprocess.run(
        ["python", "-m", "src.maisa_parser", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "1.0.0" in result.stdout


def test_cli_missing_path():
    """Verify proper exit code for missing path."""
    result = subprocess.run(
        ["python", "-m", "src.maisa_parser", "/nonexistent/path"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2  # InputError


def test_cli_success(tmp_path):
    """Verify successful parse with fixtures."""
    output = tmp_path / "output.json"
    result = subprocess.run(
        ["python", "-m", "src.maisa_parser", str(FIXTURE_DIR), "-o", str(output)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert output.exists()

    # Verify JSON structure
    import json

    with open(output) as f:
        data = json.load(f)
    assert "_schema_version" in data
    assert "health_record" in data


def test_cli_verbose(tmp_path):
    """Verify verbose flag produces INFO logs."""
    output = tmp_path / "output.json"
    result = subprocess.run(
        ["python", "-m", "src.maisa_parser", str(FIXTURE_DIR), "-o", str(output), "-v"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # INFO logs go to stderr
    assert "INFO" in result.stderr


def test_cli_quiet(tmp_path):
    """Verify quiet flag suppresses output."""
    output = tmp_path / "output.json"
    result = subprocess.run(
        ["python", "-m", "src.maisa_parser", str(FIXTURE_DIR), "-o", str(output), "-q"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    # Quiet mode should have no INFO/DEBUG/WARNING output
    assert "INFO" not in result.stderr
    assert "DEBUG" not in result.stderr


def test_cli_installed_command():
    """Test that the installed maisa-parser command works."""
    # Test --version
    result = subprocess.run(
        ["maisa-parser", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "maisa-parser" in result.stdout

    # Test --help
    result = subprocess.run(
        ["maisa-parser", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Parse Maisa" in result.stdout
