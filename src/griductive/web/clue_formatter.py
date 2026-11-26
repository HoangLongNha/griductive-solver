"""Shared clue text formatting for the React view."""
from __future__ import annotations

from typing import Any

from griductive.models import CellId


def _format_region(region: dict[str, Any], names: dict[CellId, str] | None = None) -> str:
    def label(cid: str) -> str:
        name = (names or {}).get(cid)
        return f"{name} ({cid})" if name else cid

    rtype = region.get("type")
    if rtype == "row":
        return f"Row {region['index']}"
    if rtype == "column":
        return f"Column {region['index']}"
    if rtype == "neighbors":
        return f"neighbors of {label(str(region['cell']))}"
    if rtype == "above":
        return f"cells above {label(str(region['cell']))}"
    if rtype == "below":
        return f"cells below {label(str(region['cell']))}"
    if rtype == "left_of":
        return f"cells to the left of {label(str(region['cell']))}"
    if rtype == "right_of":
        return f"cells to the right of {label(str(region['cell']))}"
    if rtype == "corners":
        return "the four corners"
    if rtype in ("edges", "boundary"):
        return "the outer edges"
    if rtype == "between":
        pair = region.get("cells", [])
        if len(pair) == 2:
            return f"between {label(str(pair[0]))} and {label(str(pair[1]))}"
    if rtype == "common_neighbors":
        pair = region.get("cells", [])
        if len(pair) == 2:
            return f"common neighbors of {label(str(pair[0]))} and {label(str(pair[1]))}"
    if rtype == "intersection":
        subs = region.get("regions", [])
        if subs:
            return " in ".join(_format_region(dict(sub), names) for sub in subs)
    if rtype == "cells":
        if region.get("label"):
            return str(region["label"])
        raw_cells = [str(c) for c in region.get("cells", [])]
        if set(raw_cells) == {"A1", "D1", "A4", "D4"} and len(raw_cells) == 4:
            return "the four corners (A1, D1, A4, D4)"
        labeled = [label(c) for c in raw_cells]
        if len(labeled) == 2:
            return f"pair [{labeled[0]} and {labeled[1]}]"
        return f"group [{', '.join(labeled)}]"
    return "region"


def _status_nouns(clue: dict[str, Any], k: int | None = None) -> str:
    is_innocent = str(clue.get("status", "CRIMINAL")).upper() == "INNOCENT"
    if k == 1:
        return "innocent" if is_innocent else "criminal"
    return "innocents" if is_innocent else "criminals"


def format_clue_text(clue: dict[str, Any], names: dict[CellId, str]) -> str:
    """Render a structured clue into readable English for the GUI."""
    def label(cid: str) -> str:
        name = names.get(cid)
        return f"{name} ({cid})" if name else cid

    kind = clue.get("kind")
    if kind == "FACT":
        status = str(clue["status"]).capitalize()
        return f"{label(clue['cell'])} is {status}."
    if kind == "SAME":
        a, b = clue["cells"]
        return f"{label(a)} and {label(b)} have the same status."
    if kind == "DIFFERENT":
        a, b = clue["cells"]
        return f"{label(a)} and {label(b)} have different statuses."
    if kind == "EXACTLY":
        k = int(clue["k"])
        noun = _status_nouns(clue, k)
        return f"Exactly {k} {noun} in {_format_region(clue['region'], names)}."
    if kind == "AT_LEAST":
        k = int(clue["k"])
        noun = _status_nouns(clue, k)
        return f"At least {k} {noun} in {_format_region(clue['region'], names)}."
    if kind == "AT_MOST":
        k = int(clue["k"])
        noun = _status_nouns(clue, k)
        return f"At most {k} {noun} in {_format_region(clue['region'], names)}."
    if kind == "PARITY":
        parity = str(clue["parity"]).lower()
        noun = _status_nouns(clue)
        return f"An {parity} number of {noun} in {_format_region(clue['region'], names)}."
    if kind == "CONNECTED":
        noun = _status_nouns(clue)
        return f"All {noun} in {_format_region(clue['region'], names)} are connected."
    if kind == "COMPOUND":
        premises = " and ".join(
            f"{label(p['cell'])} is {str(p['status']).capitalize()}"
            for p in clue.get("premises", [])
        )
        c = clue["conclusion"]
        concl = f"{label(c['cell'])} is {str(c['status']).capitalize()}"
        return f"If {premises}, then {concl}."
    return f"{kind} clue"
