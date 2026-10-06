"""Run bounded synthetic host comparisons, optionally through a routing backend."""

import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import secrets
import time
from contextlib import AsyncExitStack
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

from ...guidance import read_guidance
from ...measurements import provenance
from ...profiles import PROFILE_NAMES
from ...server import create_server
from ..experiments import (
    PROPOSED_THRESHOLDS,
    assess_comparison,
    fingerprint,
    freeze_experiment,
    source_fingerprint,
    verify_experiment,
)
from ..result_cases import FIXTURE_VERSION
from ..routing import RoutingCase, grade_routing, summarise_routing
from .anthropic import client, definitions, session
from .budget import Budget
from .models import GROK, MODEL, SONNET, model_configuration
from .result_calibration import GRADER_VERSION, calibrate
from .result_grading import claims_in_scope, fact_verdict, literal_fields, structured_answer_only
from .result_selection import (
    ResultSelectionDispatch,
    ResultTask,
    advertised_result_tools,
    development_tasks,
    prompt_names_model,
    result_tasks,
    validation_tasks,
)
from .roles import ROLE_CASES
from .routing import RoutingDispatch, complete_task_usage, routing_backend_client
from .routing_report import paired_routing_report
from .scenarios import SyntheticDispatch, answer, rlc_tasks, role_tasks, tasks
from .workflow_packet import load_workflow_packet


def _routing_origin(value):
    origin = urlsplit(value or "")
    if (
        origin.scheme not in ("http", "https")
        or not origin.hostname
        or origin.username
        or origin.password
        or origin.query
        or origin.fragment
        or origin.path not in ("", "/")
        or (origin.scheme == "http" and origin.hostname not in ("localhost", "127.0.0.1", "::1"))
    ):
        raise ValueError("Routing backend requires an HTTPS origin or loopback HTTP origin")


async def classify_routing(args):
    """Classification-only mode in the existing runner, sharing its routing ledger.

    Proposed labels can produce an offline NOT_RUN packet. Paid classification
    requires independently recorded label/calibration review, never self-review.
    """
    from ...guidance.routing import MODEL as routing_model
    from ...guidance.routing import VERSION, question
    from ..routing_cases import development_cases, selection_validation_cases

    if args.output.exists():
        raise ValueError("Refusing to overwrite evidence")
    if any(
        getattr(args, option, None)
        for option in (
            "routing_comparison",
            "workflow_suite",
            "workflow_packet",
            "results_robust",
            "role_comparison",
            "results_baseline",
        )
    ):
        raise ValueError("Classification cannot combine host comparison protocols")
    if args.samples != 1:
        raise ValueError("Classification records exactly one attempt per case; use samples=1")
    split = args.routing_classification
    cases = development_cases() if split == "development" else selection_validation_cases()
    packet_path = getattr(args, "routing_label_packet", None)
    if packet_path:
        from .workflow_packet import _reject_constant, _unique_object

        cases = [
            RoutingCase.model_validate(row)
            for row in json.loads(
                packet_path.read_text(encoding="utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        ]
    if (
        not cases
        or len({case.id for case in cases}) != len(cases)
        or len({case.request for case in cases}) != len(cases)
        or any(case.split != split for case in cases)
    ):
        raise ValueError("Classification packet requires unique cases in the selected split")
    if getattr(args, "case", None):
        raise ValueError("Classification must retain the full frozen packet")
    dry = getattr(args, "routing_dry_run", False)
    interval = getattr(args, "routing_minimum_interval", 6.1)
    if type(interval) not in (int, float) or not math.isfinite(interval) or interval < 6.1:
        raise ValueError(
            "Classification interval must be at least 6.1 seconds for default admission"
        )
    budget = Budget(args.cap_usd, args.prior_usd)
    packet_hash = fingerprint([case.model_dump() for case in cases])
    calibration = {"passed": False, "status": "NOT_RUN"}
    if not dry:
        _routing_origin(args.routing_backend_url)
        budget._decision_rate(args.routing_input_rate)
        if not os.environ.get("SIMBA_ROUTING_EVAL_API_KEY"):
            raise ValueError("Classification requires a qualified synthetic backend account")
        review_path = getattr(args, "routing_calibration_review", None)
        if not review_path or any(case.label_status != "verified" for case in cases):
            raise ValueError(
                "Paid classification requires independently reviewed labels and calibration"
            )
        calibration = json.loads(review_path.read_text(encoding="utf-8"))
        from ..routing import GRADER_VERSION

        if (
            set(calibration)
            != {"passed", "reviewer", "packet_sha256", "grader_version", "rationale"}
            or calibration.get("passed") is not True
            or calibration.get("packet_sha256") != packet_hash
            or calibration.get("grader_version") != GRADER_VERSION
            or not isinstance(calibration.get("reviewer"), str)
            or not calibration["reviewer"].strip()
            or calibration["reviewer"] in {case.author for case in cases}
            or not isinstance(calibration.get("rationale"), str)
            or not calibration["rationale"].strip()
        ):
            raise ValueError("Classification calibration review is not independently hash-bound")
    inputs = {
        "purpose": "routing_classification",
        "split": split,
        "packet": [case.model_dump() for case in cases],
        "packet_sha256": packet_hash,
        "model": routing_model,
        "question_version": VERSION,
        "question_sha256": fingerprint(question()),
        "backend_origin_sha256": fingerprint(getattr(args, "routing_backend_url", None)),
        "input_rate_usd_per_million": getattr(args, "routing_input_rate", None),
        "authorised_budget": {"cap_usd": args.cap_usd, "prior_usd": args.prior_usd},
        "dry_run": dry,
        "minimum_interval_seconds": interval,
    }
    report = {
        "status": "NOT_RUN" if dry else "running",
        "inputs": inputs,
        "calibration": calibration,
        "frozen": {
            "inputs_sha256": fingerprint(inputs),
            "source_sha256": source_fingerprint(),
            "calibration_sha256": fingerprint(calibration),
        },
        "trials": [
            {"case_id": case.id, "routing_attempts": [], "score": grade_routing(case, None)}
            for case in cases
        ],
    }
    original_path = getattr(args, "continue_from", None)
    original_hash = None
    if original_path:
        if dry:
            raise ValueError("Classification continuation requires a stopped network run")
        from .workflow_packet import _reject_constant, _unique_object

        original_bytes = original_path.read_bytes()
        original_hash = hashlib.sha256(original_bytes).hexdigest()
        previous = json.loads(
            original_bytes, object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        review_path = getattr(args, "continuation_review", None)
        if review_path is None:
            raise ValueError("Classification continuation requires source-transition review")
        transition = json.loads(review_path.read_text(encoding="utf-8"))
        old_inputs, new_inputs = deepcopy(previous["inputs"]), deepcopy(inputs)
        old_inputs["authorised_budget"].pop("prior_usd")
        new_inputs["authorised_budget"].pop("prior_usd")
        previous_budget = previous["budget"]
        if (
            previous.get("status") != "stopped"
            or old_inputs != new_inputs
            or previous["calibration"] != calibration
            or previous["frozen"]["inputs_sha256"] != fingerprint(previous["inputs"])
            or previous["frozen"]["calibration_sha256"] != fingerprint(calibration)
            or any(
                type(previous_budget.get(key)) not in (int, float)
                or not math.isfinite(previous_budget[key])
                or previous_budget[key] < 0
                for key in ("prior", "charged", "reserved")
            )
            or args.prior_usd + 1e-9
            < sum(previous_budget[key] for key in ("prior", "charged", "reserved"))
            or transition.get("verified") is not True
            or not transition.get("rationale")
            or transition.get("previous_report_sha256") != original_hash
            or transition.get("previous_source_sha256") != previous["frozen"]["source_sha256"]
            or transition.get("current_source_sha256") != report["frozen"]["source_sha256"]
        ):
            raise ValueError(
                "Classification continuation changed frozen inputs, lost spending or broke review"
            )
        old_rows = previous["trials"]
        if [row.get("case_id") for row in old_rows] != [case.id for case in cases] or any(
            row["score"].get("case_id") != case.id
            or row["score"].get("case_sha256") != fingerprint(case.model_dump())
            for case, row in zip(cases, old_rows, strict=True)
        ):
            raise ValueError("Classification continuation changed case identities")
        if all(row["score"]["status"] in ("PASS", "FAIL", "NEEDS_REVIEW") for row in old_rows):
            raise ValueError("Classification continuation has no unfinished cases")
        report["trials"] = deepcopy(old_rows)
        report["continuation"] = {
            "previous_report_sha256": original_hash,
            "source_transition": transition,
        }

    def save():
        if (
            report["frozen"]["inputs_sha256"] != fingerprint(inputs)
            or report["frozen"]["source_sha256"] != source_fingerprint()
            or report["frozen"]["calibration_sha256"] != fingerprint(calibration)
            or (
                original_path is not None
                and hashlib.sha256(original_path.read_bytes()).hexdigest() != original_hash
            )
        ):
            raise ValueError("Classification frozen inputs changed")
        report["budget"] = asdict(budget)
        report["summary"] = summarise_routing([row["score"] for row in report["trials"]])
        from collections import Counter

        report["attempt_score_counts"] = dict(
            Counter(
                score["status"]
                for row in report["trials"]
                for score in [*row.get("score_history", []), row["score"]]
            )
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temporary.replace(args.output)

    save()
    if dry:
        return
    server = create_server("compact", profile="full")
    visible = [tool.name for tool in await server.list_tools()]
    active = None
    try:
        async with routing_backend_client(
            args.routing_backend_url, os.environ["SIMBA_ROUTING_EVAL_API_KEY"]
        ) as backend:
            for index, (case, row) in enumerate(zip(cases, report["trials"], strict=True)):
                if row["score"]["status"] in ("PASS", "FAIL", "NEEDS_REVIEW"):
                    continue
                if index:
                    await asyncio.sleep(interval)
                if getattr(args, "stop_file", None) and args.stop_file.exists():
                    raise RuntimeError("Classification stopped before submission")

                previous_attempts = deepcopy(row["routing_attempts"])
                if row["score"]["status"] != "NOT_RUN":
                    row.setdefault("score_history", []).append(deepcopy(row["score"]))
                    row["score"] = grade_routing(case, None)

                def checkpoint(attempts, row=row, previous_attempts=previous_attempts):
                    row["routing_attempts"] = previous_attempts + attempts
                    save()

                dispatch = RoutingDispatch(
                    None,
                    backend,
                    budget,
                    checkpoint,
                    visible=visible,
                    input_rate=args.routing_input_rate,
                )
                active = (case, row)
                result, is_error = await dispatch("recommend_workflow", {"request": case.request})
                # Remove only the MCP presentation fields; unexpected fields stay invalid.
                envelope = {
                    key: value
                    for key, value in result.items()
                    if key
                    not in {
                        "guidance",
                        "suggested_tools",
                        "profile_limited",
                        "advisory_only",
                        "next_action",
                    }
                }
                row["score"] = grade_routing(
                    case, envelope, error="backend_error" if is_error else None
                )
                save()
                if is_error:
                    raise RuntimeError("Classification backend refused; evidence retained")
                active = None
        report["status"] = "complete"
    except BaseException as error:
        report["status"] = "stopped"
        report["error_type"] = type(error).__name__
        if active is not None and active[1]["score"]["status"] == "NOT_RUN":
            active[1]["score"] = grade_routing(active[0], None, error=type(error).__name__)
        raise
    finally:
        save()


async def run(args):
    if getattr(args, "routing_classification", None):
        return await classify_routing(args)
    if any(
        getattr(args, option, None)
        for option in ("routing_dry_run", "routing_label_packet", "routing_calibration_review")
    ):
        raise ValueError("Classification settings require explicit classification mode")
    if args.output.exists():
        raise ValueError("Refusing to overwrite evidence; carry prior spend into a new run")
    budget = Budget(
        args.cap_usd,
        args.prior_usd,
        model=getattr(args, "model", MODEL),
        reasoning_effort=getattr(args, "reasoning_effort", None),
    )
    host_client, host_definitions, host_session = client, definitions, session
    key_name = "ANTHROPIC_API_KEY"
    if budget.model == GROK:
        from . import xai

        if args.mode != "eager":
            raise ValueError("xAI evaluation supports eager tools only")
        host_client, host_definitions, host_session = xai.client, xai.definitions, xai.session
        key_name = "XAI_API_KEY"
    tool_profile = getattr(args, "tool_profile", "full")
    if tool_profile != "full" and getattr(args, "workflow_suite", None) != "rlc01":
        raise ValueError("Explicit tool profiles require the prospective RLC suite")
    grader_version = getattr(args, "grader_version", GRADER_VERSION)
    if type(grader_version) is not int or grader_version not in (17, 18, 19):
        raise ValueError("Unsupported result grader version")
    if grader_version != 17 and not (
        getattr(args, "workflow_suite", None) == "rlc01" or getattr(args, "workflow_packet", None)
    ):
        raise ValueError("Grader 18 requires an explicitly prospective workflow")
    grading_calibration = (
        calibrate() if grader_version == 17 else calibrate(grader_version=grader_version)
    )
    server = create_server("compact", profile=tool_profile)
    tools = await server.list_tools()
    role = getattr(args, "role_comparison", None)
    baseline_path = getattr(args, "results_baseline", None)
    robust = getattr(args, "results_robust", False)
    rlc = getattr(args, "workflow_suite", None) == "rlc01"
    routing_comparison = getattr(args, "routing_comparison", False)
    routing_url = getattr(args, "routing_backend_url", None)
    routing_rate = getattr(args, "routing_input_rate", None)
    if routing_comparison:
        if any(
            getattr(args, option, None)
            for option in (
                "role_comparison",
                "results_baseline",
                "results_robust",
                "results_model_diagnostic",
                "results_acceptance",
            )
        ):
            raise ValueError("Routing comparison cannot combine separate comparison protocols")
        if not rlc or args.mode != "eager" or getattr(args, "case_order_seed", None) is None:
            raise ValueError("Routing comparison requires frozen RLC eager mode and an order seed")
        _routing_origin(routing_url)
        budget._decision_rate(routing_rate)
        if not os.environ.get("SIMBA_ROUTING_EVAL_API_KEY"):
            raise ValueError("Routing comparison requires a qualified synthetic backend account")
    elif routing_url is not None or routing_rate is not None:
        raise ValueError("Routing settings require explicit routing comparison mode")
    session_timeout = getattr(args, "session_timeout_seconds", None)
    if session_timeout is not None and (not math.isfinite(session_timeout) or session_timeout <= 0):
        raise ValueError("Session timeout must be finite and positive")
    acceptance = getattr(args, "results_acceptance", False)
    selection_validation = getattr(args, "results_selection_validation", False)
    if selection_validation and not acceptance:
        raise ValueError(
            "Selection validation requires an explicitly selected reviewed case packet"
        )
    packet = getattr(args, "results_acceptance_packet", "original")
    if packet not in ("original", "fresh", "v2", "v3", "v4") or (
        packet != "original" and not acceptance
    ):
        raise ValueError("Fresh acceptance packet requires acceptance mode")
    diagnostic = getattr(args, "results_model_diagnostic", False)
    if diagnostic and (
        not robust or (acceptance and not selection_validation) or role or args.mode != "eager"
    ):
        raise ValueError("Model diagnostic requires robust eager mode without other comparisons")
    if acceptance and not robust:
        raise ValueError("Acceptance candidate cases require a frozen robust comparison")
    dataset_count = getattr(args, "results_validation_datasets", 0)
    if dataset_count and (not robust or dataset_count not in (2, 3)):
        raise ValueError("Generated validation requires robust mode and two or three datasets")
    validation_seed = None
    if robust and not (baseline_path or diagnostic):
        raise ValueError("Robust results assessment requires a paired guidance comparison")
    guidance_arms = None
    if diagnostic:
        guidance_arms = {
            "candidate": {
                s: read_guidance("results", s)
                for s in ("entrypoint", "interpretation", "tool-reference")
            }
        }
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
    if rlc and (role or baseline_path or robust or acceptance or diagnostic or dataset_count):
        raise ValueError(
            "RLC01 development suite cannot be combined with historical comparison modes"
        )
    if rlc and (budget.model != GROK or args.mode != "eager"):
        raise ValueError("RLC01 requires the explicit Grok eager route")
    workflow_packet_path = getattr(args, "workflow_packet", None)
    if workflow_packet_path and not rlc:
        raise ValueError("Workflow packets require the prospective RLC workflow suite")
    workflow_packet = load_workflow_packet(workflow_packet_path) if workflow_packet_path else None
    suite = (
        workflow_packet.triples()
        if workflow_packet
        else rlc_tasks()
        if rlc
        else role_tasks()
        if role
        else tasks()
    )
    if guidance_arms:
        if acceptance or diagnostic:
            if packet == "fresh":
                from ..result_acceptance_fresh import fresh_acceptance_tasks as acceptance_tasks
            elif packet == "v2":
                from ..result_acceptance_v2 import acceptance_v2_tasks as acceptance_tasks
            elif packet == "v3":
                from ..result_acceptance_v3 import acceptance_v3_tasks as acceptance_tasks
            elif packet == "v4":
                from ..result_acceptance_v4 import acceptance_v4_tasks as acceptance_tasks
            else:
                from ..result_acceptance import acceptance_tasks

        validation_seed = secrets.randbits(63) if dataset_count else None
        suite = [
            (task, task.prompt, task.expected)
            for task in (
                acceptance_tasks()
                if acceptance or diagnostic
                else validation_tasks(validation_seed, dataset_count)
                if dataset_count
                else development_tasks()
                if robust
                else result_tasks()
            )
        ]
    selected = [task for task in suite if args.case is None or task[0].id == args.case]
    if diagnostic and (args.samples != 2 or dataset_count):
        raise ValueError("Model diagnostic requires two repetitions on the fixed case set")
    if diagnostic and packet == "original":
        selected = [
            task
            for task in selected
            if task[0].id
            in {"acceptance_a", "acceptance_d", "acceptance_e", "acceptance_f", "acceptance_h"}
        ]
    if role:
        selected = [task for task in selected if task[0].id in ROLE_CASES[role]]
    if not selected:
        raise ValueError("No tasks match the requested comparison")
    order_seed = getattr(args, "case_order_seed", None)
    if order_seed is not None and type(order_seed) is not int:
        raise ValueError("Case order seed must be an integer")
    schedule = [list(selected) for _ in range(args.samples)]
    if order_seed is not None:
        rng = random.Random(order_seed)
        for repetition in schedule:
            rng.shuffle(repetition)
    trial_filter = getattr(args, "results_trial", None)
    if trial_filter:
        allowed_trials = {
            f"{view}:{rep}" for view in (guidance_arms or {}) for rep in range(args.samples)
        }
        if (
            not selection_validation
            or diagnostic
            or args.case is None
            or not baseline_path
            or len(set(trial_filter)) != len(trial_filter)
            or not set(trial_filter) <= allowed_trials
        ):
            raise ValueError("Trial selection requires a valid paired single-case validation")
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
            "results_acceptance": acceptance,
            "results_selection_validation": selection_validation,
            "results_acceptance_packet": packet,
            "model": budget.model,
            "model_configuration": model_configuration(budget.model, budget.reasoning_effort),
            "results_model_diagnostic": diagnostic,
            "validation_seed": validation_seed,
            "validation_datasets": dataset_count,
            "result_fixture_version": FIXTURE_VERSION if guidance_arms else None,
        },
        "trials": [],
        "catalogue": [t.model_dump(mode="json") for t in tools],
        "tasks": [
            {
                "case": c.model_dump()
                if not isinstance(c, ResultTask)
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
                    "evidence_window": c.evidence_window,
                    **({"section_windows": c.section_windows} if c.section_windows else {}),
                    **(
                        {"forbidden_result_sections": sorted(c.forbidden_result_sections)}
                        if c.forbidden_result_sections
                        else {}
                    ),
                    **(
                        {"period_evidence_granularity": c.period_evidence_granularity}
                        if c.period_evidence_granularity != "native"
                        else {}
                    ),
                    "max_response_bytes": c.max_response_bytes,
                    **(
                        {"summary_granularity_independent": True}
                        if c.summary_granularity_independent
                        else {}
                    ),
                    "allow_recovery_errors": c.allow_recovery_errors,
                    "allowed_result_sections": sorted(c.allowed_result_sections)
                    if c.allowed_result_sections is not None
                    else None,
                },
                "prompt": p,
                "expected": e,
            }
            for c, p, e in selected
        ],
    }
    if grader_version != 17:
        report["configuration"]["grader_version"] = grader_version
    if rlc:
        from .result_rlc_tasks import RLC_TASK_VERSION

        report["configuration"]["workflow_suite"] = "rlc01"
        report["configuration"]["tool_profile"] = tool_profile
        report["configuration"]["workflow_task_version"] = RLC_TASK_VERSION
        report["guidance"] = {
            "current": {
                s: read_guidance("results", s)
                for s in ("entrypoint", "interpretation", "tool-reference")
            }
        }
    if workflow_packet is not None:
        report["configuration"]["workflow_packet"] = workflow_packet.freeze()
    if routing_comparison:
        from ...guidance.routing import MODEL as routing_model
        from ...guidance.routing import VERSION as routing_version
        from ...guidance.routing import question

        packet_families = (
            {
                entry.contract.id: entry.family
                for entry in workflow_packet.document.tasks
                if entry.kind == "workflow" and entry.family
            }
            if workflow_packet is not None
            else {}
        )
        report["configuration"]["routing_comparison"] = {
            "version": "hosted-routing-v1",
            "backend_origin_sha256": fingerprint(routing_url),
            "model": routing_model,
            "question_version": routing_version,
            "question_sha256": fingerprint(question()),
            "input_rate_usd_per_million": routing_rate,
            "client_deadline_seconds": 3.25,
            "arms": ["baseline", "candidate"],
            "catalogue_policy": "Same eager domain catalogue; candidate adds advisory tool",
            "report_families": {
                c.id: packet_families.get(c.id) or getattr(c, "family", "") or c.id
                for c, _, _ in selected
            },
        }
    if session_timeout is not None or rlc:
        report["configuration"]["session_timeout_seconds"] = (
            session_timeout if session_timeout is not None else 180.0
        )
    if guidance_arms:
        report["guidance"] = guidance_arms
    if order_seed is not None:
        report["configuration"]["case_order_seed"] = order_seed
        report["configuration"]["case_order"] = [
            [case.id for case, _, _ in repetition] for repetition in schedule
        ]
    if trial_filter:
        report["configuration"]["results_trial"] = list(trial_filter)
    continue_from = getattr(args, "continue_from", None)
    completed_trials = set()
    continuation_hash = None
    if continue_from:
        if (
            (not routing_comparison and (not robust or not guidance_arms))
            or diagnostic
            or trial_filter
        ):
            raise ValueError("Continuation requires an unchanged robust paired comparison")
        previous_bytes = continue_from.read_bytes()
        previous = json.loads(previous_bytes)
        review_path = getattr(args, "continuation_review", None)
        if not review_path:
            raise ValueError("Continuation requires a reviewed source transition")
        transition = json.loads(review_path.read_text(encoding="utf-8"))
        if (
            transition.get("verified") is not True
            or not transition.get("rationale")
            or transition.get("previous_report_sha256")
            != hashlib.sha256(previous_bytes).hexdigest()
            or transition.get("previous_source_sha256")
            != previous["frozen_experiment"]["source_sha256"]
            or transition.get("current_source_sha256") != source_fingerprint()
        ):
            raise ValueError("Continuation source transition is not verified")
        previous_config = dict(previous["configuration"])
        previous_continuation = previous_config.pop("continuation", {})
        if (
            previous.get("status") != "stopped"
            or previous_config != report["configuration"]
            or any(previous[key] != report[key] for key in ("tasks", "guidance", "catalogue"))
            or previous["calibration"] != grading_calibration
            or fingerprint(previous["calibration"])
            != previous["frozen_experiment"]["calibration_sha256"]
            or any(
                previous[key] != previous["experiment_inputs"][key]
                for key in ("configuration", "tasks", "guidance", "catalogue")
            )
            or previous["frozen_experiment"]["inputs_sha256"]
            != fingerprint(previous["experiment_inputs"])
            or previous["experiment_inputs"]["acceptance_thresholds"]
            != getattr(args, "acceptance_thresholds", None)
            or args.prior_usd + 1e-9
            < sum(previous["budget"][k] for k in ("prior", "charged", "reserved"))
        ):
            raise ValueError("Continuation changed frozen inputs or lost prior spend")
        valid_keys = {
            (case.id, view, rep)
            for case, _, _ in selected
            for view in (["baseline", "candidate"] if routing_comparison else guidance_arms)
            for rep in range(args.samples)
        }
        completed_trials = {tuple(key) for key in previous_continuation.get("completed_trials", [])}
        previous_keys = [
            (row["case"], row["view"], row["repetition"]) for row in previous["trials"]
        ]
        if len(set(previous_keys)) != len(previous_keys) or not set(previous_keys) <= valid_keys:
            raise ValueError("Continuation has invalid or duplicate trial identities")
        completed_trials.update(
            (row["case"], row["view"], row["repetition"])
            for row in previous["trials"]
            if "trajectory" in row
        )
        result_case_ids = {case.id for case, _, _ in selected if isinstance(case, ResultTask)}
        for row in previous["trials"]:
            terminal_fields = (
                ("assertions", "passed", "outcome", "read_authorisation")
                if row["case"] in result_case_ids
                else ("fact_verdict", "passed", "outcome", "execution_trials")
            )
            if "trajectory" in row and (
                not all(key in row for key in terminal_fields)
                or "final_text" not in row.get("session", {})
            ):
                raise ValueError("Continuation contains an incomplete terminal record")
        if not completed_trials <= valid_keys or completed_trials == valid_keys:
            raise ValueError("Continuation has no valid unfinished trials")
        continuation_hash = hashlib.sha256(previous_bytes).hexdigest()
        report["configuration"]["continuation"] = {
            "previous_report_sha256": continuation_hash,
            "completed_trials": [list(key) for key in sorted(completed_trials)],
            "source_transition": transition,
            "policy": "Preserve completed trials; restart incomplete trials as separately billed attempts",
        }
    if robust or rlc:
        report["calibration"] = grading_calibration
        report["experiment_inputs"] = {
            "purpose": "development_smoke"
            if rlc and args.samples == 1
            else "model_selection_validation"
            if diagnostic or selection_validation or (routing_comparison and args.samples > 1)
            else "candidate_acceptance"
            if acceptance
            else "development",
            "case_review": getattr(args, "case_review", None),
            "samples": args.samples,
            "configuration": report["configuration"],
            "authorised_budget": {"cap_usd": args.cap_usd, "prior_usd": args.prior_usd},
            "acceptance_thresholds": getattr(args, "acceptance_thresholds", None),
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
        if continue_from:
            old_inputs = deepcopy(previous["experiment_inputs"])
            new_inputs = deepcopy(report["experiment_inputs"])
            for inputs in (old_inputs, new_inputs):
                inputs["configuration"].pop("continuation", None)
                inputs["authorised_budget"].pop("prior_usd", None)
            if old_inputs != new_inputs:
                raise ValueError("Continuation changed frozen experimental inputs")
        report["frozen_experiment"] = freeze_experiment(
            report["experiment_inputs"], report["calibration"]
        )

    def verify():
        if workflow_packet is not None:
            workflow_packet.verify()
        stop_file = getattr(args, "stop_file", None)
        if stop_file and stop_file.exists():
            raise RuntimeError("Operator requested stop; checkpoint and reservations retained")
        if robust or rlc:
            verify_experiment(
                report["frozen_experiment"], report["experiment_inputs"], grading_calibration
            )
        if (
            continue_from
            and hashlib.sha256(continue_from.read_bytes()).hexdigest() != continuation_hash
        ):
            raise ValueError("Original continuation evidence changed")

    def save(_=None):
        report["budget"] = asdict(budget)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        for attempt in range(10):
            try:
                temporary.replace(args.output)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                # Retry only the local atomic rename, never a provider request.
                time.sleep(0.1)

    save()
    try:
        verify()
        async with AsyncExitStack() as clients:
            provider = await clients.enter_async_context(host_client(os.environ[key_name]))
            backend_client = (
                await clients.enter_async_context(
                    routing_backend_client(routing_url, os.environ["SIMBA_ROUTING_EVAL_API_KEY"])
                )
                if routing_comparison
                else None
            )
            for rep, repetition in enumerate(schedule):
                for case, prompt, expected in repetition:
                    result_case = isinstance(case, ResultTask)
                    modes = ["eager", "deferred"] if rep % 2 == 0 else ["deferred", "eager"]
                    if args.mode != "both":
                        modes = [args.mode]
                    arms = [(mode, tool_profile if rlc else "full") for mode in modes]
                    if role:
                        arms = [("eager", "full"), ("eager", role)]
                        if rep % 2:
                            arms.reverse()
                    if guidance_arms:
                        arms = [("eager", view) for view in guidance_arms]
                        if diagnostic and case.id not in {"acceptance_a", "acceptance_e"}:
                            arms = [("eager", "candidate")]
                        if rep % 2:
                            arms.reverse()
                    if routing_comparison:
                        arms = [("eager", "baseline"), ("eager", "candidate")]
                        if rep % 2:
                            arms.reverse()
                    for mode, view in arms:
                        if (case.id, view, rep) in completed_trials:
                            continue
                        if trial_filter and f"{view}:{rep}" not in trial_filter:
                            continue
                        arm_server = (
                            server
                            if rlc or view == "full" or guidance_arms
                            else create_server("compact", profile=view)
                        )
                        visible = await arm_server.list_tools()
                        if routing_comparison and view == "baseline":
                            visible = [
                                tool for tool in visible if tool.name != "recommend_workflow"
                            ]
                        dispatch = SyntheticDispatch(
                            arm_server, case, allowed_tools=[t.name for t in visible]
                        )
                        context = ""
                        if result_case:
                            guidance = (
                                guidance_arms[view]
                                if guidance_arms
                                else report["guidance"]["current"]
                            )
                            dispatch = ResultSelectionDispatch(
                                arm_server, case, guidance=guidance, grader_version=grader_version
                            )
                            context = "\n\n".join(
                                guidance[s]["content"] for s in ("entrypoint", "interpretation")
                            )
                        paraphrased = bool(guidance_arms) and (
                            rep >= 3 or getattr(args, "results_prompt", "mixed") == "paraphrase"
                        )
                        session_prompt = (case.paraphrase or prompt) if paraphrased else prompt
                        offered = visible
                        if result_case and prompt_names_model(session_prompt, dispatch.model_hash):
                            offered = advertised_result_tools(
                                visible, session_prompt, dispatch.model_hash
                            )
                        definitions_sent = host_definitions(offered, mode)
                        row = {
                            "case": case.id,
                            "mode": mode,
                            "view": view,
                            "tool_names": [t.name for t in offered],
                            "repetition": rep,
                            "definitions_sha256": hashlib.sha256(
                                json.dumps(definitions_sent, sort_keys=True).encode()
                            ).hexdigest(),
                        }
                        if result_case:
                            row["result_tool_exposure"] = (
                                "named_hash"
                                if prompt_names_model(session_prompt, dispatch.model_hash)
                                else "catalogue"
                            )
                        report["trials"].append(row)
                        if routing_comparison:
                            row["routing_attempts"] = []
                            if view == "candidate":

                                def routing_checkpoint(attempts, row=row):
                                    row["routing_attempts"] = attempts
                                    save()
                                    verify()

                                dispatch = RoutingDispatch(
                                    dispatch,
                                    backend_client,
                                    budget,
                                    routing_checkpoint,
                                    visible=[tool.name for tool in offered],
                                    input_rate=routing_rate,
                                    profile=tool_profile,
                                )
                        if guidance_arms or rlc:
                            row["prompt"] = session_prompt
                            row["prompt_variant"] = "paraphrase" if paraphrased else "original"
                            row["grader_version"] = grader_version

                        def checkpoint(record, row=row):
                            row["session"] = record
                            if routing_comparison:
                                row["complete_task_usage"] = complete_task_usage(
                                    record, row["routing_attempts"]
                                )
                            save()
                            verify()

                        result = await host_session(
                            provider,
                            definitions_sent,
                            session_prompt,
                            dispatch,
                            budget,
                            checkpoint,
                            **({"system_context": context} if result_case else {}),
                            **(
                                {"session_timeout_seconds": session_timeout}
                                if session_timeout is not None
                                else {}
                            ),
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
                            and (result_case or dispatch.completed == len(case.steps))
                            and dispatch.errors == 0
                            and dispatch.unintended_writes == 0
                        )
                        if rlc and not result_case:
                            contract = ResultTask(case.id, prompt, frozenset(), expected)
                            row["fact_verdict"] = fact_verdict(
                                contract, actual, set(), grader_version=grader_version
                            )
                            row["claim_review_required"] = (
                                not claims_in_scope(contract, actual)
                                or not structured_answer_only(result.get("final_text", ""))
                                or row["fact_verdict"] == "review"
                            )
                            row["trajectory"] = dispatch.calls
                            row["execution_trials"] = [t.model_dump() for t in dispatch.trials]
                            row["literal_fields_match"] = literal_fields(contract, actual)
                            row["outcome"] = (
                                "fail"
                                if not row["passed"] or row["fact_verdict"] == "fail"
                                else "review"
                                if row["claim_review_required"]
                                else "pass"
                            )
                            row["passed"] = row["outcome"] == "pass"
                        if result_case:
                            row["noncontributing_result_calls"] = (
                                dispatch.noncontributing_result_calls
                            )
                            row["read_authorisation"] = {
                                key: getattr(dispatch, key)
                                for key in (
                                    "read_attempts",
                                    "actual_reads",
                                    "unauthorised_read_attempts",
                                    "unauthorised_reads",
                                )
                            }
                            row["trajectory"] = dispatch.calls
                            row["assertions"] = dispatch.grade(actual)
                            if robust or rlc:
                                row["fact_verdict"] = fact_verdict(
                                    case,
                                    actual,
                                    dispatch.supported_sections,
                                    grader_version=grader_version,
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
                            if robust or rlc:
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
                        if (result_case or rlc) and (
                            getattr(dispatch, "unauthorised_reads", 0) or dispatch.unintended_writes
                        ):
                            raise RuntimeError("Hard access safety failure; evidence retained")
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
        if routing_comparison:
            report["routing_measurements"] = paired_routing_report(
                report["trials"],
                report["configuration"]["routing_comparison"]["report_families"],
                samples=args.samples,
            )
        if rlc:
            report["assessment"] = {
                "accepted": False,
                "decision": (
                    "Packet evidence only; external protocol and independent review required"
                    if workflow_packet is not None
                    else "Single-arm development evidence; independent claim review required"
                ),
                "limitations": [
                    "Packet independence requires external review"
                    if workflow_packet is not None
                    else "Exposed synthetic cases",
                    "Paired routing experiment; independent outcome review remains required"
                    if routing_comparison
                    else "Single arm",
                    "No production latency evidence",
                ],
            }
        elif diagnostic:
            report["assessment"] = {
                "accepted": False,
                "decision": "Model-selection validation only; independent claim review required",
                "limitations": ["Reused cases", "Single arm", "Model configuration differs"],
            }
        elif robust:
            report["assessment"] = assess_comparison(
                report["trials"],
                {c.id: c.family for c, _, _ in selected},
                samples=args.samples,
                datasets={c.id: c.dataset for c, _, _ in selected},
                thresholds=getattr(args, "acceptance_thresholds", None),
            )
        save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--routing-classification", choices=("development", "selection_validation"))
    parser.add_argument(
        "--routing-minimum-interval",
        type=float,
        default=6.1,
        help="Classification pacing in seconds; minimum 6.1 for default admission",
    )
    parser.add_argument(
        "--routing-dry-run",
        action="store_true",
        help="Freeze NOT_RUN classification evidence without provider clients",
    )
    parser.add_argument(
        "--routing-label-packet",
        type=Path,
        help="Full JSON list of RoutingCase labels, reviewed before paid calls",
    )
    parser.add_argument(
        "--routing-calibration-review",
        type=Path,
        help="Independent packet/hash-bound grader review",
    )
    parser.add_argument(
        "--routing-comparison",
        action="store_true",
        help="Optional hosted advisory tool versus baseline in frozen eager RLC mode",
    )
    parser.add_argument("--routing-backend-url", help="Qualified synthetic backend origin")
    parser.add_argument(
        "--routing-input-rate",
        type=float,
        help="Actual Decisions account input price in USD per million, including premiums",
    )
    parser.add_argument(
        "--continue-from",
        type=Path,
        help="Preserve a stopped report and run only unfinished trials",
    )
    parser.add_argument(
        "--continuation-review",
        type=Path,
        help="Reviewed source-transition manifest for continuation",
    )
    parser.add_argument("--cap-usd", type=float, required=True)
    parser.add_argument("--prior-usd", type=float, default=0)
    parser.add_argument("--samples", type=int, default=2)
    parser.add_argument(
        "--grader-version",
        type=int,
        choices=(17, 18, 19),
        default=17,
        help="17 preserves historical semantics; 18 enables canonical identity for prospective workflows",
    )
    parser.add_argument("--tool-profile", choices=PROFILE_NAMES, default="full")
    parser.add_argument(
        "--workflow-packet",
        type=Path,
        help="Reviewed synthetic JSON packet for prospective RLC; does not grant acceptance",
    )
    parser.add_argument(
        "--workflow-suite", choices=("rlc01",), help="Prospective 20-case development inventory"
    )
    parser.add_argument(
        "--session-timeout-seconds", type=float, help="Explicit per-session monotonic deadline"
    )
    parser.add_argument(
        "--case-order-seed", type=int, help="Freeze shuffled case order within each repetition"
    )
    parser.add_argument(
        "--results-trial",
        action="append",
        help="Run only VIEW:REPETITION for one selection-validation case; never grants paired acceptance",
    )
    parser.add_argument("--model", choices=(MODEL, SONNET, GROK), default=MODEL)
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high", "xhigh"),
        help="xAI reasoning profile; low is the fast option, default medium",
    )
    parser.add_argument(
        "--results-model-diagnostic",
        action="store_true",
        help="Frozen single-arm validation on five reused cases, two repetitions",
    )
    parser.add_argument("--mode", choices=("eager", "deferred", "both"), default="eager")
    parser.add_argument(
        "--case", help="Exact case ID in the selected packet; unknown IDs are rejected"
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
        "--results-acceptance",
        action="store_true",
        help="Independently reviewed synthetic candidate cases; requires review manifest",
    )
    parser.add_argument("--case-review", type=Path)
    parser.add_argument(
        "--results-selection-validation",
        action="store_true",
        help="Reuse reviewed cases for selection only, never final acceptance",
    )
    parser.add_argument(
        "--results-acceptance-packet",
        choices=("original", "fresh", "v2", "v3", "v4"),
        default="original",
    )
    parser.add_argument(
        "--results-robust",
        action="store_true",
        help="Frozen development comparison with calibration and paired intervals",
    )
    args = parser.parse_args()
    if args.case_review:
        args.case_review = json.loads(args.case_review.read_text(encoding="utf-8"))
    if args.samples < 1:
        parser.error("samples must be positive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
