"""Run scripted public contracts without provider calls, sockets or real fits."""

import argparse
import asyncio
import json
import logging
from pathlib import Path

from .reporting import render
from .runner import evaluate, evaluate_roles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--description-mode", choices=("legacy", "compact"), default="legacy")
    parser.add_argument(
        "--roles", action="store_true", help="current deterministic role jobs, not paid trials"
    )
    args = parser.parse_args(argv)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    report = asyncio.run(
        evaluate_roles(args.description_mode)
        if args.roles
        else evaluate(args.samples, args.description_mode)
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "evaluation.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    if not args.roles:
        (args.output_dir / "evaluation.md").write_text(render(report), encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
