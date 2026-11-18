"""Clue logic: regions, direct semantics and CNF encoding (VT2)."""
from .regions import ClueValidationError, region_from_data, resolve_region
from .semantics import evaluate_clue, referenced_cells, validate_clue

__all__ = ['ClueValidationError', 'evaluate_clue', 'referenced_cells', 'region_from_data',
           'resolve_region', 'validate_clue']
