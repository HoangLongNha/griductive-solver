"""Offline validation utilities, strictly separate from the public Agent."""
from .uniqueness import (
    UniquenessResult,
    UniquenessStatus,
    analyze_unique_cnf,
    analyze_unique_complete,
    build_primary_blocking_clause,
    check_unique_cnf,
    check_unique_complete,
)

__all__ = [
    "UniquenessResult",
    "UniquenessStatus",
    "analyze_unique_cnf",
    "analyze_unique_complete",
    "build_primary_blocking_clause",
    "check_unique_cnf",
    "check_unique_complete",
]
