"""Deductive logic agent: public KB builder and entailment classification (VT4)."""
from .entailment import AgentVerdictOracle, classify, classify_kb, classify_one
from .knowledge_base import (
    CNFMetrics,
    KnowledgeBase,
    QueryPurpose,
    SATQuery,
    build_kb,
    run_sat_query,
    validate_public_state,
)

__all__ = [
    "AgentVerdictOracle",
    "CNFMetrics",
    "KnowledgeBase",
    "QueryPurpose",
    "SATQuery",
    "build_kb",
    "classify",
    "classify_kb",
    "classify_one",
    "run_sat_query",
    "validate_public_state",
]
