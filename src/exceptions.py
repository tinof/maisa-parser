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
