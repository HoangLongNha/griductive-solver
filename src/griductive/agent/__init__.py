"""Deductive logic agent: KB, entailment, deduction loop, trace and hint (VT4)."""
from .deduction import auto_solve, next_forced_verdict, select_forced_verdict
from .entailment import AgentVerdictOracle, classify, classify_kb, classify_one
from .hint import HintOutcome, HintResult, get_hint
from .knowledge_base import (
    CNFMetrics,
    KnowledgeBase,
    QueryPurpose,
    SATQuery,
    build_kb,
    run_sat_query,
    validate_public_state,
)
from .trace import (
    AggregatedSATStats,
    DeductionStep,
    DeductionTrace,
    TraceStatus,
    aggregate_queries,
    build_trace,
)

__all__ = [
    "AgentVerdictOracle",
    "AggregatedSATStats",
    "CNFMetrics",
    "DeductionStep",
    "DeductionTrace",
    "HintOutcome",
    "HintResult",
    "KnowledgeBase",
    "QueryPurpose",
    "SATQuery",
    "TraceStatus",
    "aggregate_queries",
    "auto_solve",
    "build_kb",
    "build_trace",
    "classify",
    "classify_kb",
    "classify_one",
    "get_hint",
    "next_forced_verdict",
    "run_sat_query",
    "select_forced_verdict",
    "validate_public_state",
]
