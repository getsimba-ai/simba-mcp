"""Run bounded synthetic host comparisons. Never connects to a live backend."""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
from dataclasses import asdict
from pathlib import Path

from ...guidance import read_guidance
from ...measurements import provenance
from ...server import create_server
from ..experiments import (
    PROPOSED_THRESHOLDS,
    assess_comparison,
    freeze_experiment,
    verify_experiment,
)
from .anthropic import MODEL, Budget, client, definitions, session
from .result_calibration import GRADER_VERSION, calibrate
from .result_grading import fact_verdict, literal_fields, structured_answer_only
from .result_selection import (
    ResultSelectionDispatch,
    development_tasks,
    result_tasks,
    validation_tasks,
)
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
    robust = getattr(args, "results_robust", False)
    dataset_count = getattr(args, "results_validation_datasets", 0)
    if dataset_count and (not robust or dataset_count not in (2, 3)):
        raise ValueError("Generated validation requires robust mode and two or three datasets")
    validation_seed = None
    if robust and not baseline_path:
        raise ValueError("Robust results assessment requires a paired guidance comparison")
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
        validation_seed = secrets.randbits(63) if dataset_count else None
        suite = [
            (task, task.prompt, task.expected)
            for task in (
                validation_tasks(validation_seed, dataset_count)
                if dataset_count
                else development_tasks()
                if robust
                else result_tasks()
            )
        ]
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
            "results_prompt": getattr(args, "results_prompt", "mixed"),
            "results_robust": robust,
            "model": MODEL,
            "validation_seed": validation_seed,
            "validation_datasets": dataset_count,
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
                    "family": c.family,
                    "channel": c.channel,
                    "allow_prediction": c.allow_prediction,
                    "evidence_options": [sorted(s) for s in c.evidence_sets()],
                    "fixture": c.fixture,
                    "dataset": c.dataset,
                },
                "prompt": p,
                "expected": e,
            }
            for c, p, e in selected
        ],
    }
    if guidance_arms:
        report["guidance"] = guidance_arms
    if robust:
        report["calibration"] = calibrate()
        report["experiment_inputs"] = {
            "purpose": "development",
            "samples": args.samples,
            "configuration": report["configuration"],
            "authorised_budget": {"cap_usd": args.cap_usd, "prior_usd": args.prior_usd},
            "tasks": report["tasks"],
            "guidance": report["guidance"],
            "catalogue": report["catalogue"],
            "proposed_thresholds": dict(PROPOSED_THRESHOLDS),
            "acceptance_prerequisites": [
                "independently reviewed labels",
                "owner-agreed thresholds",
                "externally held, previously unseen cases",
                "multiple synthetic datasets",
            ],
        }
        report["frozen_experiment"] = freeze_experiment(
            report["experiment_inputs"], report["calibration"]
        )

    def verify():
        stop_file = getattr(args, "stop_file", None)
        if stop_file and stop_file.exists():
            raise RuntimeError("Operator requested stop; checkpoint and reservations retained")
        if robust:
            verify_experiment(report["frozen_experiment"], report["experiment_inputs"], calibrate())

    def save(_=None):
        report["budget"] = asdict(budget)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)

    save()
    try:
        verify()
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
                        paraphrased = bool(guidance_arms) and (
                            rep >= 3 or getattr(args, "results_prompt", "mixed") == "paraphrase"
                        )
                        session_prompt = (case.paraphrase or prompt) if paraphrased else prompt
                        if guidance_arms:
                            row["prompt"] = session_prompt
                            row["prompt_variant"] = "paraphrase" if paraphrased else "original"
                            row["grader_version"] = GRADER_VERSION

                        def checkpoint(record, row=row):
                            row["session"] = record
                            save()
                            verify()

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
                            if robust:
                                row["fact_verdict"] = fact_verdict(
                                    case, actual, dispatch.supported_sections
                                )
                                row["claim_review_required"] = (
                                    not row["assertions"]["claims_in_scope"]
                                    or not structured_answer_only(result.get("final_text", ""))
                                    or row["fact_verdict"] == "review"
                                )
                            row["literal_fields_match"] = literal_fields(case, actual)
                            row["passed"] = all(row["assertions"].values())
                            row["answer_correct"] = row["assertions"]["facts"]
                            row["observed_sections"] = sorted(dispatch.observed_sections)
                            row["extra_sections"] = sorted(
                                dispatch.observed_sections - case.required_sections
                            )
                            row["execution_trials"] = [t.model_dump() for t in dispatch.trials]
                            if robust:
                                definite_failure = row["fact_verdict"] == "fail" or not all(
                                    row["assertions"][key]
                                    for key in (
                                        "required_evidence",
                                        "no_errors",
                                        "no_unintended_writes",
                                        "executed",
                                    )
                                )
                                row["outcome"] = (
                                    "fail"
                                    if definite_failure
                                    else "review"
                                    if row["claim_review_required"]
                                    else "pass"
                                )
                                row["passed"] = row["outcome"] == "pass"
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
        if robust:
            report["assessment"] = assess_comparison(
                report["trials"],
                {c.id: c.family for c, _, _ in selected},
                samples=args.samples,
                datasets={c.id: c.dataset for c, _, _ in selected},
            )
        save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cap-usd", type=float, required=True)
    parser.add_argument("--prior-usd", type=float, default=0)
    parser.add_argument("--samples", type=int, default=2)
    parser.add_argument("--mode", choices=("eager", "deferred", "both"), default="eager")
    parser.add_argument(
        "--case",
        choices=[case.id for case, _, _ in role_tasks()] + [t.id for t in development_tasks()],
    )
    parser.add_argument("--role-comparison", choices=tuple(ROLE_CASES))
    parser.add_argument(
        "--results-baseline", type=Path, help="Frozen guidance responses for paired results trials"
    )
    parser.add_argument("--results-prompt", choices=("mixed", "paraphrase"), default="mixed")
    parser.add_argument(
        "--results-validation-datasets",
        type=int,
        default=0,
        help="Generate two or three fresh synthetic datasets after guidance selection",
    )
    parser.add_argument(
        "--stop-file", type=Path, help="Stop at the next provider checkpoint if this file exists"
    )
    parser.add_argument(
        "--results-robust",
        action="store_true",
        help="Frozen development comparison with calibration and paired intervals",
    )
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("samples must be positive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
