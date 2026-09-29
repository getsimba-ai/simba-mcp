"""Run a paid, synthetic native-discovery comparison. Never connects to a live backend."""

import argparse
import asyncio
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

from ...measurements import provenance
from ...server import create_server
from .anthropic import Budget, client, definitions, session
from .scenarios import SyntheticDispatch, answer, tasks


async def run(args):
    if args.output.exists():
        raise ValueError("Refusing to overwrite evidence; carry prior spend into a new run")
    budget = Budget(args.cap_usd, args.prior_usd)
    server = create_server("compact")
    tools = await server.list_tools()
    selected = [task for task in tasks() if args.case is None or task[0].id == args.case]
    report = {
        "schema_version": 1,
        "status": "running",
        "provenance": provenance(),
        "configuration": {"mode": args.mode, "samples": args.samples, "case": args.case},
        "trials": [],
        "catalogue": [t.model_dump(mode="json") for t in tools],
        "tasks": [{"case": c.model_dump(), "prompt": p, "expected": e} for c, p, e in selected],
    }

    def save(_=None):
        report["budget"] = asdict(budget)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)

    save()
    try:
        async with client(os.environ["ANTHROPIC_API_KEY"]) as provider:
            for rep in range(args.samples):
                for case, prompt, expected in selected:
                    modes = ["eager", "deferred"] if rep % 2 == 0 else ["deferred", "eager"]
                    if args.mode != "both":
                        modes = [args.mode]
                    for mode in modes:
                        dispatch = SyntheticDispatch(server, case)
                        definitions_sent = definitions(tools, mode)
                        row = {
                            "case": case.id,
                            "mode": mode,
                            "repetition": rep,
                            "definitions_sha256": hashlib.sha256(
                                json.dumps(definitions_sent, sort_keys=True).encode()
                            ).hexdigest(),
                        }
                        report["trials"].append(row)

                        def checkpoint(record, row=row):
                            row["session"] = record
                            save()

                        result = await session(
                            provider, definitions_sent, prompt, dispatch, budget, checkpoint
                        )
                        actual, strict = answer(result.get("final_text", ""))
                        if isinstance(actual, dict) and set(actual) == {"channel_summary"}:
                            actual = actual["channel_summary"]
                        if isinstance(actual, list) and len(actual) == 1:
                            actual = actual[0]
                        row.update(
                            {
                                "strict_json": strict,
                                "answer_correct": actual == expected,
                                "steps_completed": dispatch.completed,
                                "unexpected_errors": dispatch.errors,
                                "unintended_writes": dispatch.unintended_writes,
                            }
                        )
                        row["passed"] = (
                            actual == expected
                            and dispatch.completed == len(case.steps)
                            and dispatch.errors == 0
                            and dispatch.unintended_writes == 0
                        )
                        save()
                        print(
                            json.dumps(
                                {k: row[k] for k in ("case", "mode", "repetition", "passed")}
                            ),
                            flush=True,
                        )
        report["status"] = "complete"
    except Exception as error:
        report["status"] = "stopped"
        report["error_type"] = type(error).__name__
        raise
    finally:
        save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cap-usd", type=float, required=True)
    parser.add_argument("--prior-usd", type=float, default=0)
    parser.add_argument("--samples", type=int, default=2)
    parser.add_argument("--mode", choices=("eager", "deferred", "both"), default="eager")
    parser.add_argument("--case", choices=[case.id for case, _, _ in tasks()])
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("samples must be positive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
