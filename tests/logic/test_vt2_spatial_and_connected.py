"""Tests for VT2 upgrades: spatial regions, INNOCENT counting, and 4-connected extension."""
from __future__ import annotations

import pytest

from cnf_check import assert_clue_equivalent
from griductive.logic import (
    ClueValidationError,
    encode_clue,
    evaluate_clue,
    referenced_cells,
    resolve_region,
    validate_clue,
)
from griductive.logic.cardinality import AuxPool
from griductive.models import Clue
from griductive.web.clue_formatter import format_clue_text


def clue(kind: str, **data) -> Clue:
    return Clue("c", kind, data)


def test_spatial_regions_resolve_accurately() -> None:
    assert resolve_region({"type": "corners"}, 3) == ("A1", "C1", "A3", "C3")
    assert resolve_region({"type": "edges"}, 3) == (
        "A1", "B1", "C1", "A2", "C2", "A3", "B3", "C3"
    )
    assert resolve_region({"type": "above", "cell": "B3"}, 3) == ("B1", "B2")
    assert resolve_region({"type": "below", "cell": "B1"}, 3) == ("B2", "B3")
    assert resolve_region({"type": "left_of", "cell": "C2"}, 3) == ("A2", "B2")
    assert resolve_region({"type": "right_of", "cell": "A2"}, 4) == ("B2", "C2", "D2")
    assert resolve_region({"type": "between", "cells": ["A1", "D1"]}, 4) == ("B1", "C1")
    assert resolve_region({"type": "between", "cells": ["B4", "B1"]}, 4) == ("B2", "B3")
    assert resolve_region({"type": "common_neighbors", "cells": ["A1", "C1"]}, 3) == ("B1", "B2")
    assert resolve_region(
        {
            "type": "intersection",
            "regions": [
                {"type": "neighbors", "cell": "B2"},
                {"type": "column", "index": "C"},
            ],
        },
        3,
    ) == ("C1", "C2", "C3")


@pytest.mark.parametrize(
    "bad_region",
    [
        {"type": "above", "cell": "A1"},
        {"type": "below", "cell": "A3"},
        {"type": "left_of", "cell": "A2"},
        {"type": "right_of", "cell": "C2"},
        {"type": "between", "cells": ["A1", "B1"]},  # adjacent -> 0 cells between
        {"type": "between", "cells": ["A1", "C3"]},  # diagonal -> not aligned
        {"type": "common_neighbors", "cells": ["A1", "C3"]},  # only B2? wait on 4x4 A1 & D4 have 0
        {"type": "intersection", "regions": [{"type": "row", "index": 1}]},
        {"type": "intersection", "regions": [{"type": "row", "index": 1}, {"type": "row", "index": 2}]},
    ],
)
def test_empty_or_misaligned_spatial_regions_rejected(bad_region: dict) -> None:
    size = 4 if bad_region.get("type") == "common_neighbors" else 3
    if bad_region.get("type") == "common_neighbors":
        bad_region = {"type": "common_neighbors", "cells": ["A1", "D4"]}
    with pytest.raises(ClueValidationError):
        resolve_region(bad_region, size)


@pytest.mark.parametrize("kind", ["EXACTLY", "AT_LEAST", "AT_MOST"])
def test_innocent_counting_semantics_and_cnf_equivalence(kind: str) -> None:
    region = {
        "type": "intersection",
        "regions": [{"type": "neighbors", "cell": "B2"}, {"type": "column", "index": "B"}],
    }
    for k in (0, 1, 2):
        c = clue(kind, k=k, status="INNOCENT", region=region)
        clauses = encode_clue(c, 3, AuxPool(9))
        assert_clue_equivalent(c, 3, clauses, 9)

    with pytest.raises(ClueValidationError):
        validate_clue(clue(kind, k=1, status="SUSPECT", region=region), 3)


def test_connected_orthogonality_vs_diagonal_and_cnf_equivalence() -> None:
    row1 = {"type": "row", "index": 1}
    c_row = clue("CONNECTED", status="INNOCENT", region=row1)
    a_connected = {
        "A1": False, "B1": False, "C1": True,
        "A2": True, "B2": True, "C2": True,
        "A3": True, "B3": True, "C3": True,
    }
    a_split = {
        "A1": False, "B1": True, "C1": False,
        "A2": True, "B2": True, "C2": True,
        "A3": True, "B3": True, "C3": True,
    }
    assert evaluate_clue(c_row, a_connected, 3)
    assert not evaluate_clue(c_row, a_split, 3)

    # Diagonal contact in a 2x2 neighborhood is NOT connected unless linked orthogonally
    c_box = clue("CONNECTED", status="CRIMINAL", region={"type": "cells", "cells": ["A1", "B1", "A2", "B2"]})
    a_diag = {
        "A1": True, "B1": False, "C1": False,
        "A2": False, "B2": True, "C2": False,
        "A3": False, "B3": False, "C3": False,
    }
    assert not evaluate_clue(c_box, a_diag, 3)

    for test_clue in (
        c_row,
        c_box,
        clue("CONNECTED", status="CRIMINAL", region={"type": "corners"}),
    ):
        clauses = encode_clue(test_clue, 3, AuxPool(9))
        assert_clue_equivalent(test_clue, 3, clauses, 9)
        assert len(referenced_cells(test_clue, 3)) >= 3


def test_clue_formatter_renders_natural_spatial_and_innocent_text() -> None:
    names = {"A1": "Alice", "A4": "Mara", "D1": "Dung", "A5": "Abel"}
    assert (
        format_clue_text(
            {
                "kind": "EXACTLY",
                "k": 2,
                "status": "INNOCENT",
                "region": {
                    "type": "intersection",
                    "regions": [
                        {"type": "neighbors", "cell": "A4"},
                        {"type": "column", "index": "B"},
                    ],
                },
            },
            names,
        )
        == "Exactly 2 of Mara's neighbors in Column B are innocents."
    )
    assert (
        format_clue_text(
            {
                "kind": "CONNECTED",
                "status": "INNOCENT",
                "region": {"type": "right_of", "cell": "A5"},
            },
            names,
        )
        == "The innocents to the right of Abel are connected."
    )
    assert (
        format_clue_text(
            {
                "kind": "EXACTLY",
                "k": 1,
                "region": {"type": "cells", "label": "the Cooks", "cells": ["B1", "D1"]},
            },
            names,
        )
        == "There is only 1 criminal in the Cooks."
    )


def test_clue_formatter_handles_at_least_and_at_most_boundaries() -> None:
    names = {"A1": "Alice", "B1": "Bao"}
    pair_reg = {"type": "cells", "cells": ["A1", "B1"]}

    # AT_LEAST boundaries on a 2-person pair (k=0 must NOT say "Both...", k=n says "Both...")
    assert (
        format_clue_text({"kind": "AT_LEAST", "k": 0, "region": pair_reg}, names, size=3)
        == "At least 0 of Alice and Bao are criminals."
    )
    assert (
        format_clue_text({"kind": "AT_LEAST", "k": 1, "region": pair_reg}, names, size=3)
        == "At least 1 of Alice and Bao is criminal."
    )
    assert (
        format_clue_text({"kind": "AT_LEAST", "k": 2, "region": pair_reg}, names, size=3)
        == "Both Alice and Bao are criminals."
    )

    # AT_MOST boundaries on a 2-person pair (k=0 says "Neither...", k=1 says "Not both...", k=n=2 must NOT say "Not both...")
    assert (
        format_clue_text({"kind": "AT_MOST", "k": 0, "region": pair_reg}, names, size=3)
        == "Neither Alice nor Bao is criminal."
    )
    assert (
        format_clue_text({"kind": "AT_MOST", "k": 1, "region": pair_reg}, names, size=3)
        == "Not both of Alice and Bao are criminals."
    )
    assert (
        format_clue_text({"kind": "AT_MOST", "k": 2, "region": pair_reg}, names, size=3)
        == "At most 2 of Alice and Bao are criminals."
    )

    # Row boundaries k=0 and k=n
    row_reg = {"type": "row", "index": 1}
    assert (
        format_clue_text({"kind": "AT_LEAST", "k": 0, "region": row_reg}, names, size=3)
        == "There are at least 0 criminals in Row 1."
    )
    assert (
        format_clue_text({"kind": "AT_LEAST", "k": 3, "region": row_reg}, names, size=3)
        == "Everyone in Row 1 is criminal."
    )
    assert (
        format_clue_text({"kind": "AT_MOST", "k": 0, "region": row_reg}, names, size=3)
        == "No one in Row 1 is criminal."
    )
