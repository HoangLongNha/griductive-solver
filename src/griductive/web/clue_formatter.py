"""Shared clue text formatting for the React view."""
from __future__ import annotations

from typing import Any

from griductive.models import CellId


def _format_region(region: dict[str, Any]) -> str:
    rtype = region.get("type")
    if rtype == "row":
        return f"Row {region['index']}"
    if rtype == "column":
        return f"Column {region['index']}"
    if rtype == "neighbors":
        return f"neighbors of {region['cell']}"
    if rtype == "cells":
        return f"cells [{', '.join(region.get('cells', []))}]"
    return "region"


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
        noun = "criminal" if k == 1 else "criminals"
        return f"Exactly {k} {noun} in {_format_region(clue['region'])}."
    if kind == "AT_LEAST":
        k = int(clue["k"])
        noun = "criminal" if k == 1 else "criminals"
        return f"At least {k} {noun} in {_format_region(clue['region'])}."
    if kind == "AT_MOST":
        k = int(clue["k"])
        noun = "criminal" if k == 1 else "criminals"
        return f"At most {k} {noun} in {_format_region(clue['region'])}."
    if kind == "PARITY":
        parity = str(clue["parity"]).lower()
        return f"An {parity} number of criminals in {_format_region(clue['region'])}."
    if kind == "COMPOUND":
        premises = " and ".join(
            f"{label(p['cell'])} is {str(p['status']).capitalize()}"
            for p in clue.get("premises", [])
        )
        c = clue["conclusion"]
        concl = f"{label(c['cell'])} is {str(c['status']).capitalize()}"
        return f"If {premises}, then {concl}."
    return f"{kind} clue"



