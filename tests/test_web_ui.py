"""Smoke tests for FakeController and Web UI HTTP endpoints."""
from __future__ import annotations

import http.client
import json
import shutil
import threading
import urllib.request
from pathlib import Path

import pytest

from griductive.web.fake_controller import FakeController
from griductive.web.server import create_server


def _request(url: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict | str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=5) as resp:
        raw = resp.read().decode("utf-8")
        ctype = resp.headers.get("Content-Type", "")
        if "application/json" in ctype:
            return resp.status, json.loads(raw)
        return resp.status, raw


def test_web_api_and_static_flow():
    root = Path(__file__).resolve().parents[1]
    server = create_server(host="127.0.0.1", port=0, puzzles_dir=root / "puzzles", web_dir=root / "web")
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"

    try:
        # Static assets
        code, html = _request(f"{base}/")
        assert code == 200
        assert "app.jsx" in html

        code, jsx = _request(f"{base}/app.jsx")
        assert code == 200
        assert "Detective's Caseboard" in jsx
        assert "e.target !== e.currentTarget" in jsx

        # Centralized asset manifest and diegetic SVG UI assets
        for asset in [
            "/asset-manifest.js",
            "/assets/ui/stamp_criminal.svg",
            "/assets/ui/stamp_innocent.svg",
            "/assets/ui/pin_brass.svg",
            "/assets/ui/rotary-phone.webp",
            "/assets/ui/fortune-teller/portrait.webp",
            "/assets/characters/char_01/portrait.webp",
            "/assets/characters/char_25/portrait.webp",
            "/assets/environments/detective-office/background.webp",
            "/assets/environments/detective-office/midground.webp",
            "/assets/environments/detective-office/foreground.webp",
        ]:
            req = urllib.request.Request(f"{base}{asset}", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                assert resp.status == 200
                assert len(resp.read()) > 50

        # List puzzles & initial state
        code, puzzles = _request(f"{base}/api/puzzles")
        assert code == 200
        assert any(p["id"] == "tutorial_3x3" for p in puzzles["puzzles"])

        code, state = _request(f"{base}/api/game/state")
        assert code == 200
        assert state["puzzle_id"] == "tutorial_3x3"
        # Privacy check: face-down cards must not expose status or clue
        facedown = [c for c in state["cards"] if not c["revealed"]]
        assert facedown
        assert all(c["known_status"] is None and c["clue"] is None for c in facedown)

        # CONTRADICTED check on B1 (A1 clue says B1 is INNOCENT)
        code, res = _request(f"{base}/api/game/verdict", "POST", {"cell": "B1", "status": "CRIMINAL"})
        assert res["outcome"] == "CONTRADICTED"
        assert res["newly_revealed"] is None

        # NOT_PROVABLE check on C3 at step 0
        code, res = _request(f"{base}/api/game/verdict", "POST", {"cell": "C3", "status": "INNOCENT"})
        assert res["outcome"] == "NOT_PROVABLE"

        # Hint check
        code, hint = _request(f"{base}/api/game/hint")
        assert hint["status"] == "FOUND"
        assert hint["cell"] == "B1"
        assert hint["suggested_verdict"] == "INNOCENT"

        # ACCEPTED check on B1
        code, res = _request(f"{base}/api/game/verdict", "POST", {"cell": "B1", "status": "INNOCENT"})
        assert res["outcome"] == "ACCEPTED"
        assert res["newly_revealed"] == "B1"

        # Auto solve finishes tutorial_3x3
        code, auto = _request(f"{base}/api/game/auto-solve", "POST")
        assert auto["terminal_status"] == "SOLVED"
        assert auto["state"]["solved"] is True

        # Restart resets back to initial_revealed
        code, restarted = _request(f"{base}/api/game/restart", "POST")
        assert restarted["revealed_count"] == 1
        assert restarted["solved"] is False
    finally:
        server.shutdown()
        server.server_close()



def test_static_server_blocks_prefix_sibling_traversal(tmp_path: Path) -> None:
    """[P2] Ensure sibling directories sharing prefix (web_private) cannot be read."""
    root = Path(__file__).resolve().parents[1]
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    sibling = tmp_path / "web_private"
    sibling.mkdir()
    (sibling / "probe.txt").write_text("SECRET_PROBE", encoding="utf-8")

    server = create_server(host="127.0.0.1", port=0, puzzles_dir=root / "puzzles", web_dir=web_dir)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/../web_private/probe.txt")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8")
        conn.close()
        assert resp.status == 404
        assert "SECRET_PROBE" not in body
    finally:
        server.shutdown()
        server.server_close()


def test_failed_puzzle_load_preserves_active_session(tmp_path: Path) -> None:
    """[P2] Loading a malformed puzzle must fail cleanly without wiping current game progress."""
    root = Path(__file__).resolve().parents[1]
    puzzles_dir = tmp_path / "puzzles"
    (puzzles_dir / "3x3").mkdir(parents=True)
    shutil.copy(root / "puzzles" / "3x3" / "tutorial_3x3.json", puzzles_dir / "3x3" / "tutorial_3x3.json")

    bad_data = json.loads((root / "puzzles" / "3x3" / "tutorial_3x3.json").read_text(encoding="utf-8"))
    bad_data["id"] = "broken_missing_clue"
    del bad_data["cards"][0]["clue"]
    (puzzles_dir / "3x3" / "broken_missing_clue.json").write_text(json.dumps(bad_data), encoding="utf-8")

    ctrl = FakeController(puzzles_dir)
    res = ctrl.submit_verdict("B1", "INNOCENT")
    assert res["outcome"] == "ACCEPTED"
    before = ctrl.get_public_state_dict()
    assert before["puzzle_id"] == "tutorial_3x3"
    assert before["revealed_count"] == 2

    with pytest.raises((KeyError, ValueError)):
        ctrl.load_puzzle("broken_missing_clue")

    after = ctrl.get_public_state_dict()
    assert after == before
