"""Shared baseline contracts. Integration additions remain subject to role review."""
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Protocol, Mapping
from types import MappingProxyType
import re

CellId = str  # e.g. "A1"; row-major A1, B1, C1, A2, ...
Var = int     # 1-based positive variable ID; negative integer = negated literal
Clause = tuple[int, ...]

class Status(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"

class VerdictStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    INCONSISTENT = "INCONSISTENT"

class Inference(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"
    UNKNOWN = "UNKNOWN"
    INCONSISTENT = "INCONSISTENT"

@dataclass(frozen=True)
class Region:
    type: Literal["row", "column", "neighbors", "cells"]
    index: int | str | None = None
    cell: CellId | None = None
    cells: tuple[CellId, ...] = ()

@dataclass(frozen=True)
class Clue:
    id: str
    kind: Literal["FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST", "PARITY", "COMPOUND"]
    data: Mapping  # recursively frozen, detached from caller data

    def __post_init__(self):
        object.__setattr__(self, "data", _freeze(self.data))

@dataclass(frozen=True)
class PublicCard:
    cell: CellId
    name: str
    profession: str
    revealed: bool
    known_status: Status | None
    clue: Clue | None

    def __post_init__(self):
        if not self.revealed and (self.known_status is not None or self.clue is not None):
            raise ValueError("Face-down cards cannot expose status or clue")

@dataclass(frozen=True)
class PublicState:
    puzzle_id: str
    size: int
    cards: tuple[PublicCard, ...]  # row-major

@dataclass(frozen=True)
class CNF:
    clauses: tuple[Clause, ...]
    primary_count: int
    variable_count: int  # includes all auxiliary variables
    # IDs 1..primary_count are primary; aux begin primary_count+1

@dataclass(frozen=True)
class SATStats:
    decisions: int
    propagations: int
    backtracks: int
    runtime_s: float

@dataclass(frozen=True)
class SATResult:
    is_sat: bool
    assignment: dict[int, bool] | None  # COMPLETE 1..variable_count if SAT
    stats: SATStats

@dataclass(frozen=True)
class SubmitResult:
    outcome: VerdictStatus
    state: PublicState
    newly_revealed: CellId | None
    message: str = ""


def _freeze(value):
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported clue value: {type(value).__name__}")


def _check_size(size: int) -> None:
    if type(size) is not int or not 1 <= size <= 26:
        raise ValueError("Board size must be an integer in 1..26")


def cell_to_var(cell: CellId, size: int) -> Var:
    """Map A1,B1,...,A2 to 1-based primary variables."""
    _check_size(size)
    if not isinstance(cell, str) or not re.fullmatch(r"[A-Z][1-9][0-9]*", cell):
        raise ValueError("Invalid cell ID")
    column, row = ord(cell[0]) - ord("A"), int(cell[1:]) - 1
    if not (0 <= column < size and 0 <= row < size):
        raise ValueError("Cell outside board")
    return row * size + column + 1


def var_to_cell(var: Var, size: int) -> CellId:
    _check_size(size)
    if type(var) is not int or not 1 <= var <= size * size:
        raise ValueError("Not a primary variable")
    row, column = divmod(var - 1, size)
    return f"{chr(ord('A') + column)}{row + 1}"


class VerdictOracle(Protocol):
    def classify_one(self, state: PublicState, cell: CellId) -> Inference: ...


class PublicGamePort(Protocol):
    def snapshot(self) -> PublicState: ...
    def submit_verdict(self, cell: CellId, status: Status) -> SubmitResult: ...


class SolverTimeout(TimeoutError):
    """An unfinished query; never interpret as UNSAT."""


class SolverCancelled(Exception):
    """An explicitly cancelled query; no logical verdict is available."""
