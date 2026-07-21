"""Evidence-based confidence policy for structured-document mapping."""

from __future__ import annotations

from techdoc_parser.core import SourceLocation

CONFIDENCE_FIELDS = frozenset(
    {
        "classification_confidence",
        "confidence",
        "extraction_confidence",
        "ocr_confidence",
        "provenance_confidence",
        "structure_confidence",
    }
)


def normalize_confidence(value: object, *, field_name: str) -> float | None:
    """Return a valid confidence value, or ``None`` when unavailable."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must not be boolean.")
    if not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be numeric or None.")
    normalized = float(value)
    if normalized < 0.0 or normalized > 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0.")
    return normalized


def map_source_extraction_confidence(source: SourceLocation | None) -> float | None:
    """Do not promote current SourceLocation confidence placeholders."""
    return None


def map_ocr_confidence(source: SourceLocation | None) -> float | None:
    """Return OCR confidence only when the source explicitly identifies OCR."""
    if source is None or source.confidence is None:
        return None
    method = (source.extraction_method or "").strip().lower()
    if not method.startswith("ocr"):
        return None
    return normalize_confidence(source.confidence, field_name="ocr_confidence")


def map_structure_confidence(evidence: object) -> float | None:
    """Current structural heuristics expose no calibrated confidence value."""
    return None


def add_confidence_if_available(
    data: dict[str, object],
    field_name: str,
    value: object,
) -> None:
    """Add a confidence field only when a valid value is available."""
    if field_name not in CONFIDENCE_FIELDS:
        raise ValueError(f"Unsupported confidence field: {field_name!r}.")
    normalized = normalize_confidence(value, field_name=field_name)
    if normalized is not None:
        data[field_name] = normalized


__all__ = [
    "CONFIDENCE_FIELDS",
    "add_confidence_if_available",
    "map_ocr_confidence",
    "map_source_extraction_confidence",
    "map_structure_confidence",
    "normalize_confidence",
]
