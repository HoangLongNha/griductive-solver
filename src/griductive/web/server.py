"""Lightweight stdlib HTTP server serving the React UI and Controller API."""
from __future__ import annotations

import json
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from griductive.web.fake_controller import FakeController


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    puzzles_dir: Path | None = None,
    web_dir: Path | None = None,
) -> ThreadingHTTPServer:
    root = Path(__file__).resolve().parents[3]
    puzzles_path = puzzles_dir or (root / "puzzles")
    static_path = (web_dir or (root / "web")).resolve()
    controller = FakeController(puzzles_path)
    lock = threading.Lock()

    class GriductiveHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            # Keep terminal output clean during interactive play
            pass

        def _send_json(self, code: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def _serve_static(self, rel_path: str) -> None:
            clean = "index.html" if rel_path in ("", "/") else rel_path.lstrip("/")
            target = (static_path / clean).resolve()
            if not str(target).startswith(str(static_path)) or not target.is_file():
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return
            mime, _ = mimetypes.guess_type(str(target))
            if target.suffix == ".jsx":
                mime = "text/babel; charset=utf-8"
            elif mime and mime.startswith("text/"):
                mime = f"{mime}; charset=utf-8"
            data = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            try:
                if path == "/api/puzzles":
                    with lock:
                        self._send_json(HTTPStatus.OK, {"puzzles": controller.list_puzzles()})
                    return
                if path == "/api/game/state":
                    with lock:
                        self._send_json(HTTPStatus.OK, controller.get_public_state_dict())
                    return
                if path == "/api/game/hint":
                    with lock:
                        self._send_json(HTTPStatus.OK, controller.get_hint())
                    return
                self._serve_static(path)
            except Exception as exc:  # noqa: BLE001
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            try:
                body = self._read_json()
                with lock:
                    if path == "/api/game/load":
                        puzzle_id = str(body.get("puzzle_id", ""))
                        state = controller.load_puzzle(puzzle_id)
                        self._send_json(HTTPStatus.OK, state)
                        return
                    if path == "/api/game/verdict":
                        cell = str(body.get("cell", ""))
                        status = str(body.get("status", ""))
                        result = controller.submit_verdict(cell, status)
                        self._send_json(HTTPStatus.OK, result)
                        return
                    if path == "/api/game/restart":
                        state = controller.restart()
                        self._send_json(HTTPStatus.OK, state)
                        return
                    if path == "/api/game/auto-solve":
                        result = controller.auto_solve()
                        self._send_json(HTTPStatus.OK, result)
                        return
                self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Unknown endpoint: {path}"})
            except FileNotFoundError as exc:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
            except (ValueError, KeyError, json.JSONDecodeError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    return ThreadingHTTPServer((host, port), GriductiveHandler)
