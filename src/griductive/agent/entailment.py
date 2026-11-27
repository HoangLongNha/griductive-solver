"""Entailment classification via refutation queries over the public KB (task 4.1).

Entailment rules (CONTRACTS §5):
1. Check `KB` itself for satisfiability first.
   - If `KB` is UNSAT -> every unresolved cell is `Inference.INCONSISTENT`.
2. Otherwise, for each unresolved cell `Ci` (primary variable `v`):
   - Model witness reuse optimization:
     Since `base_res.is_sat` is True, a complete satisfying assignment `M`
     (`base_res.assignment`) already witnesses one polarity for every `v`:
     * If `M[v] == True`, `KB ∧ (+v)` is already proved SAT -> test ONLY `KB ∧ (-v)`:
       - UNSAT -> `Inference.CRIMINAL` (KB |= Ci)
       - SAT   -> `Inference.UNKNOWN`
     * If `M[v] == False`, `KB ∧ (-v)` is already proved SAT -> test ONLY `KB ∧ (+v)`:
       - UNSAT -> `Inference.INNOCENT` (KB |= ¬Ci)
       - SAT   -> `Inference.UNKNOWN`
   - Fallback (if a test/mock solver returns `assignment=None`):
     Test `KB ∧ (-v)` first and short-circuit immediately to `Inference.CRIMINAL`
     if UNSAT; otherwise test `KB ∧ (+v)`.
"""
from collections.abc import Mapping

from griductive.models import CellId, Inference, PublicState, cell_to_var

from .knowledge_base import KnowledgeBase, QueryPurpose, SATQuery, build_kb, run_sat_query


def _infer_cell_from_sat_kb(
    kb: KnowledgeBase,
    cell: CellId,
    solver,
    *,
    purpose: QueryPurpose,
    query_log: list[SATQuery] | None,
    witness_assignment: Mapping[int, bool] | None = None,
) -> Inference:
    """Classify one cell assuming base `kb` has already been verified SAT."""
    var = cell_to_var(cell, kb.size)

    if witness_assignment is not None and var in witness_assignment:
        if witness_assignment[var]:
            # KB ∧ (+var) is already witnessed SAT by base_res.assignment.
            neg_res = run_sat_query(
                solver,
                kb.cnf,
                (-var,),
                purpose=purpose,
                target_cell=cell,
                query_log=query_log,
            )
            return Inference.CRIMINAL if not neg_res.is_sat else Inference.UNKNOWN

        # KB ∧ (-var) is already witnessed SAT by base_res.assignment.
        pos_res = run_sat_query(
            solver,
            kb.cnf,
            (var,),
            purpose=purpose,
            target_cell=cell,
            query_log=query_log,
        )
        return Inference.INNOCENT if not pos_res.is_sat else Inference.UNKNOWN

    # Fallback when solver returns SAT without an assignment witness: short-circuit on UNSAT.
    neg_res = run_sat_query(
        solver,
        kb.cnf,
        (-var,),
        purpose=purpose,
        target_cell=cell,
        query_log=query_log,
    )
    if not neg_res.is_sat:
        return Inference.CRIMINAL

    pos_res = run_sat_query(
        solver,
        kb.cnf,
        (var,),
        purpose=purpose,
        target_cell=cell,
        query_log=query_log,
    )
    if not pos_res.is_sat:
        return Inference.INNOCENT
    return Inference.UNKNOWN


def classify_kb(
    kb: KnowledgeBase,
    solver,
    *,
    purpose: QueryPurpose = QueryPurpose.CLASSIFY,
    query_log: list[SATQuery] | None = None,
) -> dict[CellId, Inference]:
    """Classify every unresolved cell in `kb` (in row-major key order)."""
    if not kb.unresolved_cells:
        return {}

    base_res = run_sat_query(
        solver,
        kb.cnf,
        (),
        purpose=QueryPurpose.BASE_KB,
        target_cell=None,
        query_log=query_log,
    )
    if not base_res.is_sat:
        return {cell: Inference.INCONSISTENT for cell in kb.unresolved_cells}

    return {
        cell: _infer_cell_from_sat_kb(
            kb,
            cell,
            solver,
            purpose=purpose,
            query_log=query_log,
            witness_assignment=base_res.assignment,
        )
        for cell in kb.unresolved_cells
    }


def classify(public: PublicState, encoder, solver) -> dict[CellId, Inference]:
    """Classify all unresolved cells from a `PublicState` snapshot."""
    kb = build_kb(public, encoder)
    return classify_kb(kb, solver)


def classify_one(
    public: PublicState,
    cell: CellId,
    encoder,
    solver,
    *,
    purpose: QueryPurpose = QueryPurpose.VERDICT_RECHECK,
    query_log: list[SATQuery] | None = None,
) -> Inference:
    """Classify a single board cell against the public KB (used by `VerdictOracle`)."""
    kb = build_kb(public, encoder)
    cell_to_var(cell, kb.size)  # Validate cell coordinate before querying

    base_res = run_sat_query(
        solver,
        kb.cnf,
        (),
        purpose=QueryPurpose.BASE_KB,
        target_cell=None,
        query_log=query_log,
    )
    if not base_res.is_sat:
        return Inference.INCONSISTENT

    return _infer_cell_from_sat_kb(
        kb,
        cell,
        solver,
        purpose=purpose,
        query_log=query_log,
        witness_assignment=base_res.assignment,
    )


class AgentVerdictOracle:
    """`VerdictOracle` adapter delegating provability checks to the agent's entailment engine."""

    def __init__(self, encoder, solver, query_log: list[SATQuery] | None = None):
        self._encoder = encoder
        self._solver = solver
        self.query_log = query_log

    def classify_one(self, state: PublicState, cell: CellId) -> Inference:
        return classify_one(
            state,
            cell,
            self._encoder,
            self._solver,
            purpose=QueryPurpose.VERDICT_RECHECK,
            query_log=self.query_log,
        )
