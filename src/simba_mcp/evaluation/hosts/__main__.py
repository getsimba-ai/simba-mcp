"""Run bounded synthetic host comparisons. Never connects to a live backend."""

import argparse
import asyncio
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path

from ...guidance import read_guidance
from ...measurements import provenance
from ...server import create_server
from .anthropic import Budget, client, definitions, session
from .result_selection import ResultSelectionDispatch, literal_fields, result_tasks
from .roles import ROLE_CASES
from .scenarios import SyntheticDispatch, answer, role_tasks, tasks


async def run(args):
    if args.output.exists():
        raise ValueError("Refusing to overwrite evidence; carry prior spend into a new run")
    budget = Budget(args.cap_usd, args.prior_usd)
    server = create_server("compact")
    tools = await server.list_tools()
    role = getattr(args, "role_comparison", None)
    baseline_path = getattr(args, "results_baseline", None)
    guidance_arms = None
    if baseline_path:
        if role or args.mode != "eager":
            raise ValueError("Results comparison requires eager mode and no role comparison")
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        required = ("entrypoint", "interpretation", "tool-reference")
        if set(baseline) != set(required) or any(
            not isinstance(baseline[s].get("content"), str) for s in required
        ):
            raise ValueError("Baseline must contain the three frozen results guidance responses")
        guidance_arms = {
            "baseline": baseline,
            "candidate": {s: read_guidance("results", s) for s in required},
        }
    if role is not None and args.mode != "eager":
        raise ValueError("Role comparison requires eager mode to isolate catalogue visibility")
    suite = role_tasks() if role else tasks()
    if guidance_arms:
        suite = [(task, task.prompt, task.expected) for task in result_tasks()]
    selected = [task for task in suite if args.case is None or task[0].id == args.case]
    if role:
        selected = [task for task in selected if task[0].id in ROLE_CASES[role]]
    if not selected:
        raise ValueError("No tasks match the requested comparison")
    report = {
        "schema_version": 1,
        "status": "running",
        "provenance": provenance(),
        "configuration": {
            "mode": args.mode,
            "samples": args.samples,
            "case": args.case,
            "role_comparison": role,
            "results_comparison": bool(guidance_arms),
        },
        "trials": [],
        "catalogue": [t.model_dump(mode="json") for t in tools],
        "tasks": [
            {
                "case": c.model_dump()
                if not guidance_arms
                else {
                    "id": c.id,
                    "required_sections": sorted(c.required_sections),
                    "paraphrase": c.paraphrase,
                },
                "prompt": p,
                "expected": e,
            }
            for c, p, e in selected
        ],
    }
    if guidance_arms:
        report["guidance"] = guidance_arms

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
                    arms = [(mode, "full") for mode in modes]
                    if role:
                        arms = [("eager", "full"), ("eager", role)]
                        if rep % 2:
                            arms.reverse()
                    if guidance_arms:
                        arms = [("eager", "baseline"), ("eager", "candidate")]
                        if rep % 2:
                            arms.reverse()
                    for mode, view in arms:
                        arm_server = (
                            server
                            if view == "full" or guidance_arms
                            else create_server("compact", profile=view)
                        )
                        visible = await arm_server.list_tools()
                        dispatch = SyntheticDispatch(
                            arm_server, case, allowed_tools=[t.name for t in visible]
                        )
                        context = ""
                        if guidance_arms:
                            guidance = guidance_arms[view]
                            dispatch = ResultSelectionDispatch(arm_server, case, guidance=guidance)
                            context = "\n\n".join(
                                guidance[s]["content"] for s in ("entrypoint", "interpretation")
                            )
                        definitions_sent = definitions(visible, mode)
                        row = {
                            "case": case.id,
                            "mode": mode,
                            "view": view,
                            "tool_names": [t.name for t in visible],
                            "repetition": rep,
                            "definitions_sha256": hashlib.sha256(
                                json.dumps(definitions_sent, sort_keys=True).encode()
                            ).hexdigest(),
                        }
                        report["trials"].append(row)
                        session_prompt = case.paraphrase if guidance_arms and rep >= 3 else prompt
                        if guidance_arms:
                            row["prompt"] = session_prompt
                            row["prompt_variant"] = "paraphrase" if rep >= 3 else "original"
                            row["grader_version"] = 2

                        def checkpoint(record, row=row):
                            row["session"] = record
                            save()

                        result = await session(
                            provider,
                            definitions_sent,
                            session_prompt,
                            dispatch,
                            budget,
                            checkpoint,
                            **({"system_context": context} if guidance_arms else {}),
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
                            and (bool(guidance_arms) or dispatch.completed == len(case.steps))
                            and dispatch.errors == 0
                            and dispatch.unintended_writes == 0
                        )
                        if guidance_arms:
                            row["assertions"] = dispatch.grade(actual)
                            row["literal_fields_match"] = literal_fields(case, actual)
                            row["passed"] = all(row["assertions"].values())
                            row["answer_correct"] = row["assertions"]["facts"]
                            row["observed_sections"] = sorted(dispatch.observed_sections)
                            row["extra_sections"] = sorted(
                                dispatch.observed_sections - case.required_sections
                            )
                            row["execution_trials"] = [t.model_dump() for t in dispatch.trials]
                        save()
                        print(
                            json.dumps(
                                {
                                    k: row[k]
                                    for k in ("case", "mode", "view", "repetition", "passed")
                                }
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
    parser.add_argument(
        "--case", choices=[case.id for case, _, _ in role_tasks()] + [t.id for t in result_tasks()]
    )
    parser.add_argument("--role-comparison", choices=tuple(ROLE_CASES))
    parser.add_argument(
        "--results-baseline", type=Path, help="Frozen guidance responses for paired results trials"
    )
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("samples must be positive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
