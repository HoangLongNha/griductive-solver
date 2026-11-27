"""Shared clue text formatting for the React view — natural Knotwise detective prose."""
from __future__ import annotations

from typing import Any

from griductive.logic.regions import resolve_region
from griductive.models import CellId


def _person_label(cid: str, names: dict[CellId, str] | None) -> str:
    name = (names or {}).get(cid)
    return name if name else cid


def _region_cardinality(region: dict[str, Any], size: int | None) -> int | None:
    if size is None:
        return None
    try:
        return len(resolve_region(region, size))
    except Exception:
        return None


def _format_region_phrase(
    region: dict[str, Any],
    names: dict[CellId, str] | None = None,
) -> tuple[str, str]:
    """Return (mode, phrase) where mode is 'in' (e.g. 'Row 1'), 'prep' (e.g. 'above Alice'),
    'neighbors' (possessive neighbor phrase), 'common_neighbors', 'corners', 'edges', or 'group'."""
    def person(cid: str) -> str:
        return _person_label(str(cid), names)

    rtype = region.get("type")
    if rtype == "row":
        return "in", f"Row {region['index']}"
    if rtype == "column":
        return "in", f"Column {region['index']}"
    if rtype == "neighbors":
        return "neighbors", person(region["cell"])
    if rtype == "above":
        return "prep", f"above {person(region['cell'])}"
    if rtype == "below":
        return "prep", f"below {person(region['cell'])}"
    if rtype == "left_of":
        return "prep", f"to the left of {person(region['cell'])}"
    if rtype == "right_of":
        return "prep", f"to the right of {person(region['cell'])}"
    if rtype == "corners":
        return "corners", "the four corners"
    if rtype in ("edges", "boundary"):
        return "edges", "the outer edges"
    if rtype == "between":
        pair = region.get("cells", [])
        if len(pair) == 2:
            return "prep", f"between {person(pair[0])} and {person(pair[1])}"
    if rtype == "common_neighbors":
        pair = region.get("cells", [])
        if len(pair) == 2:
            return "common_neighbors", f"{person(pair[0])} and {person(pair[1])}"
    if rtype == "intersection":
        subs = [dict(s) for s in region.get("regions", [])]
        if len(subs) == 2:
            m0, p0 = _format_region_phrase(subs[0], names)
            m1, p1 = _format_region_phrase(subs[1], names)
            if m0 == "neighbors" and m1 == "in":
                return "neighbors_in", f"{p0}|{p1}"
            if m1 == "neighbors" and m0 == "in":
                return "neighbors_in", f"{p1}|{p0}"
        if subs:
            parts = []
            for s in subs:
                m, p = _format_region_phrase(s, names)
                parts.append(f"{p}'s neighbors" if m == "neighbors" else p)
            return "in", " and ".join(parts)
    if rtype == "cells":
        if region.get("label"):
            return "in", str(region["label"])
        raw_cells = [str(c) for c in region.get("cells", [])]
        if set(raw_cells) in ({"A1", "C1", "A3", "C3"}, {"A1", "D1", "A4", "D4"}, {"A1", "E1", "A5", "E5"}) and len(raw_cells) == 4:
            return "corners", "the four corners"
        people = [person(c) for c in raw_cells]
        if len(people) == 2:
            return "pair", f"{people[0]} and {people[1]}"
        if len(people) == 3:
            return "group", f"{people[0]}, {people[1]}, and {people[2]}"
        return "group", ", ".join(people)
    return "in", "the group"


def _status_word(clue: dict[str, Any], *, plural: bool = False) -> str:
    is_innocent = str(clue.get("status", "CRIMINAL")).upper() == "INNOCENT"
    if plural:
        return "innocents" if is_innocent else "criminals"
    return "innocent" if is_innocent else "criminal"


def _opposite_status_word(clue: dict[str, Any], *, plural: bool = False) -> str:
    is_innocent = str(clue.get("status", "CRIMINAL")).upper() == "INNOCENT"
    if plural:
        return "criminals" if is_innocent else "innocents"
    return "criminal" if is_innocent else "innocent"


def _format_exactly(clue: dict[str, Any], names: dict[CellId, str], size: int | None) -> str:
    k = int(clue["k"])
    reg = dict(clue["region"])
    n = _region_cardinality(reg, size)
    mode, phrase = _format_region_phrase(reg, names)
    s_sing = _status_word(clue, plural=False)
    s_plur = _status_word(clue, plural=True)
    noun = s_sing if k == 1 else s_plur

    if mode == "neighbors":
        if k == 0:
            return f"{phrase} has no {s_sing} neighbors."
        if n == 2 and k == 2:
            return f"Both of {phrase}'s neighbors are {s_plur}."
        if n is not None and k == n:
            return f"All {n} of {phrase}'s neighbors are {s_plur}."
        if k == 1:
            return f"Exactly 1 of {phrase}'s neighbors is {s_sing}."
        return f"{phrase} has {k} {s_sing} neighbors."

    if mode == "neighbors_in":
        who, where = phrase.split("|", 1)
        if k == 0:
            return f"None of {who}'s neighbors in {where} are {s_plur}."
        if k == 1:
            return f"Exactly 1 of {who}'s neighbors in {where} is {s_sing}."
        return f"Exactly {k} of {who}'s neighbors in {where} are {s_plur}."

    if mode == "common_neighbors":
        if k == 0:
            return f"{phrase} share no {s_sing} neighbors."
        if n == 2 and k == 2:
            return f"Both common neighbors of {phrase} are {s_plur}."
        if k == 1:
            return f"Only 1 common neighbor of {phrase} is {s_sing}."
        return f"{phrase} share {k} {s_sing} neighbors."

    if mode == "corners":
        if k == 0:
            return f"None of the four corners are {s_plur}."
        if k == 4:
            return f"All four corners are {s_plur}."
        if k == 1:
            return f"Only 1 of the four corners is {s_sing}."
        return f"Exactly {k} of the four corners are {s_plur}."

    if mode == "edges":
        if k == 0:
            return f"No one on the outer edges is {s_sing}."
        if k == 1:
            return f"Only 1 person on the outer edges is {s_sing}."
        return f"There are {k} {s_plur} on the outer edges."

    if mode == "pair":
        if k == 0:
            return f"Neither {phrase.replace(' and ', ' nor ')} is {s_sing}."
        if k == 1:
            return f"Only 1 of {phrase} is {s_sing}."
        return f"Both {phrase} are {s_plur}."

    if mode == "group":
        if k == 0:
            return f"None of {phrase} are {s_plur}."
        if k == 1:
            return f"Only 1 of {phrase} is {s_sing}."
        return f"Exactly {k} of {phrase} are {s_plur}."

    if mode == "prep":
        if k == 0:
            if n == 2:
                return f"Neither person {phrase} is {s_sing}."
            return f"No one {phrase} is {s_sing}."
        if n == 2 and k == 2:
            return f"Both people {phrase} are {s_plur}."
        if n is not None and k == n and n >= 3:
            return f"All {n} people {phrase} are {s_plur}."
        if k == 1:
            if n == 2:
                return f"Only 1 of the 2 people {phrase} is {s_sing}."
            return f"There is 1 {s_sing} {phrase}."
        return f"There are {k} {s_plur} {phrase}."

    # Default mode == "in" (Row / Column)
    if k == 0:
        return f"No one in {phrase} is {s_sing}."
    if n is not None and k == n:
        return f"Everyone in {phrase} is {s_sing}."
    if k == 1:
        return f"There is only 1 {s_sing} in {phrase}."
    return f"There are {k} {noun} in {phrase}."


def _format_at_least(clue: dict[str, Any], names: dict[CellId, str], size: int | None) -> str:
    k = int(clue["k"])
    reg = dict(clue["region"])
    n = _region_cardinality(reg, size)
    mode, phrase = _format_region_phrase(reg, names)
    s_sing = _status_word(clue, plural=False)
    s_plur = _status_word(clue, plural=True)

    if k == 0:
        if mode == "corners":
            return f"At least 0 of the four corners are {s_plur}."
        if mode == "neighbors":
            return f"At least 0 of {phrase}'s neighbors are {s_plur}."
        if mode == "pair":
            return f"At least 0 of {phrase} are {s_plur}."
        if mode == "prep":
            return f"There are at least 0 {s_plur} {phrase}."
        return f"There are at least 0 {s_plur} in {phrase}."
    if n is not None and k == n:
        return _format_exactly(clue, names, size)
    if mode == "corners":
        if k == 1:
            return f"At least 1 of the four corners is {s_sing}."
        return f"At least {k} of the four corners are {s_plur}."
    if mode == "neighbors":
        if k == 1:
            return f"At least 1 of {phrase}'s neighbors is {s_sing}."
        return f"At least {k} of {phrase}'s neighbors are {s_plur}."
    if mode == "pair":
        if k == 1:
            return f"At least 1 of {phrase} is {s_sing}."
        return f"Both {phrase} are {s_plur}."
    if mode == "prep":
        if k == 1:
            return f"There is at least 1 {s_sing} {phrase}."
        return f"There are at least {k} {s_plur} {phrase}."
    if k == 1:
        return f"There is at least 1 {s_sing} in {phrase}."
    return f"There are at least {k} {s_plur} in {phrase}."


def _format_at_most(clue: dict[str, Any], names: dict[CellId, str], size: int | None) -> str:
    k = int(clue["k"])
    if k == 0:
        return _format_exactly(clue, names, size)
    reg = dict(clue["region"])
    mode, phrase = _format_region_phrase(reg, names)
    s_sing = _status_word(clue, plural=False)
    s_plur = _status_word(clue, plural=True)
    noun = s_sing if k == 1 else s_plur

    if mode == "neighbors":
        if k == 1:
            return f"At most 1 of {phrase}'s neighbors is {s_sing}."
        return f"At most {k} of {phrase}'s neighbors are {s_plur}."
    if mode == "pair":
        if k == 1:
            return f"Not both of {phrase} are {s_plur}."
        return f"At most {k} of {phrase} are {s_plur}."
    if mode == "prep":
        return f"There are at most {k} {noun} {phrase}."
    if k == 1:
        return f"There is at most 1 {s_sing} in {phrase}."
    return f"There are at most {k} {noun} in {phrase}."


def format_clue_text(
    clue: dict[str, Any],
    names: dict[CellId, str],
    size: int | None = None,
) -> str:
    """Render a structured clue into natural Knotwise-style English for the GUI."""
    def person(cid: str) -> str:
        return _person_label(str(cid), names)

    kind = clue.get("kind")
    if kind == "FACT":
        is_innocent = str(clue["status"]).upper() == "INNOCENT"
        word = "innocent" if is_innocent else "a criminal"
        return f"{person(clue['cell'])} is {word}."
    if kind == "SAME":
        a, b = clue["cells"]
        return f"{person(a)} and {person(b)} share the same verdict."
    if kind == "DIFFERENT":
        a, b = clue["cells"]
        return f"One of {person(a)} and {person(b)} is a criminal, the other is innocent."
    if kind == "EXACTLY":
        return _format_exactly(clue, names, size)
    if kind == "AT_LEAST":
        return _format_at_least(clue, names, size)
    if kind == "AT_MOST":
        return _format_at_most(clue, names, size)
    if kind == "PARITY":
        parity = str(clue["parity"]).lower()
        s_plur = _status_word(clue, plural=True)
        mode, phrase = _format_region_phrase(dict(clue["region"]), names)
        if mode == "neighbors":
            return f"{phrase} has an {parity} number of {s_plur} among their neighbors."
        if mode == "prep":
            return f"There is an {parity} number of {s_plur} {phrase}."
        return f"{phrase} has an {parity} number of {s_plur}."
    if kind == "CONNECTED":
        s_plur = _status_word(clue, plural=True)
        mode, phrase = _format_region_phrase(dict(clue["region"]), names)
        if mode == "neighbors":
            return f"The {s_plur} neighboring {phrase} are connected."
        if mode == "prep":
            return f"The {s_plur} {phrase} are connected."
        if mode in ("corners", "edges"):
            return f"The {s_plur} on {phrase} are connected."
        return f"The {s_plur} in {phrase} are connected."
    if kind == "COMPOUND":
        def lit_text(item: dict[str, Any]) -> str:
            w = "innocent" if str(item["status"]).upper() == "INNOCENT" else "a criminal"
            return f"{person(item['cell'])} is {w}"
        premises = " and ".join(lit_text(p) for p in clue.get("premises", []))
        concl = lit_text(clue["conclusion"])
        return f"If {premises}, then {concl}."
    return f"{kind} clue"
