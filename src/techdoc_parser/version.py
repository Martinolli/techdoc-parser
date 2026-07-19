"""Package and export contract version metadata."""

PARSER_NAME = "techdoc-parser"
SCHEMA_VERSION = "0.1.0"
PARSER_VERSION = "0.1.0"


def get_export_metadata() -> dict[str, object]:
    """Return metadata included in exported machine-readable artifacts."""
    return {
        "schema_version": SCHEMA_VERSION,
        "parser": {
            "name": PARSER_NAME,
            "version": PARSER_VERSION,
        },
    }


__all__ = [
    "PARSER_NAME",
    "PARSER_VERSION",
    "SCHEMA_VERSION",
    "get_export_metadata",
]
