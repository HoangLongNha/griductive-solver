"""No-guess deduction loop and deterministic step selection (task 4.2).

Rules (CONTRACTS §5):
- Never submit or reveal an `UNKNOWN` cell.
- When multiple cells are forced, always pick the first one in row-major order.
- After every accepted reveal, take a fresh `snapshot()`, rebuild KB, and repeat.
- Terminate with `SOLVED` (all revealed), `STUCK` (no entailed move), or
  `INCONSISTENT` (unsatisfiable public KB or contradiction on submission).
"""
from collections.abc import Callable, Mapping
from time import perf_counter

from griductive.models import (
    CellId,
    Inference,
    PublicGamePort,
    PublicState,
    Status,
    VerdictStatus,
)

from .entailment import classify_kb
from .knowledge_base import SATQuery, build_kb, validate_public_state
from .trace import (
    DeductionStep,
    DeductionTrace,
    TraceStatus,
    aggregate_queries,
    build_trace,
)


def select_forced_verdict(
    public: PublicState,
    inferences: Mapping[CellId, Inference],
) -> tuple[CellId, Status] | None:
    """Return the first forced `(cell, status)` in row-major order, or `None`."""
    ordered_cards = validate_public_state(public)
    for card in ordered_cards:
        if card.revealed:
            continue
        inference = inferences.get(card.cell)
        if inference == Inference.CRIMINAL:
            return (card.cell, Status.CRIMINAL)
        if inference == Inference.INNOCENT:
            return (card.cell, Status.INNOCENT)
    return None


def next_forced_verdict(
    public: PublicState,
    encoder,
    solver,
) -> tuple[CellId, Status] | None:
    """Classify the public KB and select the first row-major forced verdict, if any."""
    kb = build_kb(public, encoder)
    inferences = classify_kb(kb, solver)
    return select_forced_verdict(public, inferences)


def _revealed_clue_id(state: PublicState, cell: CellId | None) -> str | None:
    if cell is None:
        return None
    for card in state.cards:
        if card.cell == cell and card.revealed and card.clue is not None:
            return card.clue.id
    return None


def _extract_oracle(game: PublicGamePort):
    """Retrieve oracle adapter if present on the game port or session."""
    if hasattr(game, "_oracle"):
        return getattr(game, "_oracle")
    if hasattr(game, "oracle"):
        return getattr(game, "oracle")
    return None


def auto_solve(
    game: PublicGamePort,
    encoder,
    solver,
    *,
    on_step: Callable[[DeductionStep], None] | None = None,
    oracle_query_log: list[SATQuery] | None = None,
) -> DeductionTrace:
    """Run the no-guess deduction loop over `PublicGamePort` until terminal status.

    If `on_step` is provided, it is invoked right after each accepted deduction
    step so Controllers/GUIs can stream live updates without waiting for the
    entire run to finish.

    `oracle_query_log` allows passing a shared query log channel with the engine's
    VerdictOracle, enabling deduction steps and trace to capture verification
    queries (Contracts §7) even when `game` is a pure `PublicGamePort` adapter
    without exposing `_oracle`.
    """
    run_start = perf_counter()
    steps: list[DeductionStep] = []
    cumulative_queries: list[SATQuery] = []

    # Ensure engine verdict verification queries are tracked (Contracts §7)
    oracle = _extract_oracle(game)
    oracle_log = oracle_query_log
    if oracle_log is None and oracle is not None:
        oracle_log = getattr(oracle, "query_log", None)
        if oracle_log is None:
            try:
                oracle_log = []
                setattr(oracle, "query_log", oracle_log)
            except (AttributeError, TypeError):
                oracle_log = None

    while True:
        step_start = perf_counter()
        state = game.snapshot()
        kb = build_kb(state, encoder)

        if not kb.unresolved_cells:
            return build_trace(
                puzzle_id=state.puzzle_id,
                status=TraceStatus.SOLVED,
                steps=steps,
                terminal_queries=(),
                total_runtime_s=perf_counter() - run_start,
                final_state=state,
                message="All cells revealed",
            )

        step_queries: list[SATQuery] = []
        inferences = classify_kb(kb, solver, query_log=step_queries)

        if any(inf == Inference.INCONSISTENT for inf in inferences.values()):
            return build_trace(
                puzzle_id=state.puzzle_id,
                status=TraceStatus.INCONSISTENT,
                steps=steps,
                terminal_queries=step_queries,
                total_runtime_s=perf_counter() - run_start,
                final_state=state,
                message="Public knowledge base is inconsistent",
            )

        forced = select_forced_verdict(state, inferences)
        if forced is None:
            return build_trace(
                puzzle_id=state.puzzle_id,
                status=TraceStatus.STUCK,
                steps=steps,
                terminal_queries=step_queries,
                total_runtime_s=perf_counter() - run_start,
                final_state=state,
                message="No entailed verdict available",
            )

        cell, verdict = forced
        oracle_idx_before = len(oracle_log) if oracle_log is not None else 0

        submit_res = game.submit_verdict(cell, verdict)

        # Collect any SAT queries executed by the engine during verdict verification (Contracts §7)
        recheck_queries = ()
        if oracle_log is not None and len(oracle_log) > oracle_idx_before:
            recheck_queries = tuple(oracle_log[oracle_idx_before:])

        combined_step_queries = tuple(step_queries) + recheck_queries

        if submit_res.outcome == VerdictStatus.ACCEPTED:
            next_state = submit_res.state
            validate_public_state(next_state)
            remaining = sum(1 for card in next_state.cards if not card.revealed)
            if remaining >= len(kb.unresolved_cells):
                return build_trace(
                    puzzle_id=state.puzzle_id,
                    status=TraceStatus.INCONSISTENT,
                    steps=steps,
                    terminal_queries=combined_step_queries,
                    total_runtime_s=perf_counter() - run_start,
                    final_state=next_state,
                    message="Game port accepted verdict without revealing a card",
                )

            cumulative_queries.extend(combined_step_queries)
            step = DeductionStep(
                step_index=len(steps) + 1,
                active_clue_ids=kb.active_clue_ids,
                cnf_metrics=kb.metrics,
                queries=combined_step_queries,
                cell=cell,
                verdict=verdict,
                outcome=submit_res.outcome,
                newly_revealed_cell=submit_res.newly_revealed,
                newly_revealed_clue_id=_revealed_clue_id(next_state, submit_res.newly_revealed),
                stats=aggregate_queries(combined_step_queries),
                cumulative_stats=aggregate_queries(cumulative_queries),
                step_runtime_s=perf_counter() - step_start,
            )
            steps.append(step)
            if on_step is not None:
                on_step(step)
            continue

        if submit_res.outcome in (VerdictStatus.CONTRADICTED, VerdictStatus.INCONSISTENT):
            return build_trace(
                puzzle_id=state.puzzle_id,
                status=TraceStatus.INCONSISTENT,
                steps=steps,
                terminal_queries=combined_step_queries,
                total_runtime_s=perf_counter() - run_start,
                final_state=submit_res.state,
                message=submit_res.message or f"Verdict rejected: {submit_res.outcome.value}",
            )

        return build_trace(
            puzzle_id=state.puzzle_id,
            status=TraceStatus.STUCK,
            steps=steps,
            terminal_queries=combined_step_queries,
            total_runtime_s=perf_counter() - run_start,
            final_state=submit_res.state,
            message=submit_res.message or "Verdict not provable",
        )
