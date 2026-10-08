"""The `yoko` command. Only `serve` exists in Phase 0; the rest are placeholders."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

# subcommand -> phase that implements it
PLANNED: dict[str, int] = {
    "import": 8,
    "replay": 6,
    "run": 7,
    "plan": 7,
    "bench": 9,
    "gen": 8,
    "export": 8,
    "oracle": 2,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yoko", description="yoko-env command line")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="run the web app (API + studio)")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    for name, phase in PLANNED.items():
        sub.add_parser(name, help=f"not implemented yet (Phase {phase})")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        import uvicorn

        uvicorn.run("yoko_server.app:app", host=args.host, port=args.port)
        return 0
    print(
        f"yoko {args.command}: not implemented yet (Phase {PLANNED[args.command]})", file=sys.stderr
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
