"""Clue logic: regions, direct semantics and CNF encoding (VT2)."""
from .encoder import active_clue_ids, cnf_counts, encode_clue, encode_full_clues, encode_kb
from .regions import ClueValidationError, region_from_data, resolve_region
from .semantics import evaluate_clue, referenced_cells, validate_clue

__all__ = ['ClueValidationError', 'active_clue_ids', 'cnf_counts', 'encode_clue',
           'encode_full_clues', 'encode_kb', 'evaluate_clue', 'referenced_cells',
           'region_from_data', 'resolve_region', 'validate_clue']
