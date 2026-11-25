#!/usr/bin/env python3
"""Entry point for the Griductive Solver Web UI."""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from griductive.web.server import create_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Griductive Solver React Web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--open", action="store_true", help="Open browser automatically")
    parser.add_argument("--timeout", type=float, default=10.0,
                        help="Total proof time limit per command, in seconds (default: 10)")
    args = parser.parse_args()

    server = create_server(host=args.host, port=args.port, solve_timeout_s=args.timeout)
    url = f"http://{args.host}:{args.port}"
    print(f"Griductive UI running at {url} (Ctrl+C to stop)")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
