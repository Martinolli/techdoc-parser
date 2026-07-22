"""Offline compatibility gates for downstream structured-document consumers."""

from techdoc_parser.compatibility.aviationrag_gate import (
    AviationRAGCompatibilityGateResult,
    AviationRAGValidatorResult,
    CompatibilityCheck,
    aviationrag_compatibility_gate_result_to_dict,
    aviationrag_compatibility_gate_result_to_json,
    run_aviationrag_compatibility_gate,
    run_aviationrag_validator,
    write_aviationrag_compatibility_report,
)

__all__ = [
    "AviationRAGCompatibilityGateResult",
    "AviationRAGValidatorResult",
    "CompatibilityCheck",
    "aviationrag_compatibility_gate_result_to_dict",
    "aviationrag_compatibility_gate_result_to_json",
    "run_aviationrag_compatibility_gate",
    "run_aviationrag_validator",
    "write_aviationrag_compatibility_report",
]
