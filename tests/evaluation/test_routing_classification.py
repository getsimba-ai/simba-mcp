"""Classification mode uses the existing adapter; synthetic review metadata only."""

import hashlib
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest

from simba_mcp.api_client import SimbaAPIClient
from simba_mcp.evaluation.experiments import fingerprint, source_fingerprint
from simba_mcp.evaluation.hosts import __main__ as command
from simba_mcp.evaluation.routing import GRADER_VERSION
from simba_mcp.evaluation.routing_cases import development_cases


@pytest.fixture
def anyio_backend():
    return "asyncio"


def arguments(tmp_path, **changes):
    return SimpleNamespace(
        **{
            "output": tmp_path / "classification.json",
            "routing_classification": "development",
            "routing_dry_run": True,
            "samples": 1,
            "cap_usd": 1,
            "prior_usd": 0,
            "routing_backend_url": "https://example.invalid",
            "routing_input_rate": 0.1,
            **changes,
        }
    )


def reviewed_packet(tmp_path):
    # These reviewer strings exercise gates; they do not independently review labels.
    cases = [
        case.model_copy(update={"label_status": "verified", "reviewer": "synthetic-test-reviewer"})
        for case in development_cases()[:2]
    ]
    labels = tmp_path / "labels.json"
    labels.write_text(json.dumps([case.model_dump() for case in cases]))
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                "passed": True,
                "reviewer": "synthetic-test-reviewer",
                "rationale": "Mechanical contract fixture, not actual independent calibration",
                "packet_sha256": fingerprint([case.model_dump() for case in cases]),
                "grader_version": GRADER_VERSION,
            }
        )
    )
    return cases, labels, review


@pytest.mark.anyio
async def test_dry_packet_retains_all_not_run_cases_without_any_clients(tmp_path, monkeypatch):
    def forbidden(*_, **__):
        raise AssertionError("Dry run must not open a provider or backend")

    monkeypatch.setattr(command, "routing_backend_client", forbidden)
    args = arguments(tmp_path)
    await command.run(args)
    result = json.loads(args.output.read_text())
    assert result["status"] == "NOT_RUN"
    assert result["summary"]["counts"] == {"NOT_RUN": 80}
    assert result["summary"]["routed_precision"]["rate"] is None
    assert result["calibration"]["passed"] is False
    assert result["budget"]["charged"] == result["budget"]["reserved"] == 0
    with pytest.raises(ValueError, match="overwrite"):
        await command.run(args)


@pytest.mark.anyio
async def test_unreviewed_network_packet_rejected_before_output_or_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("SIMBA_ROUTING_EVAL_API_KEY", "synthetic-backend")
    args = arguments(tmp_path, routing_dry_run=False)
    with pytest.raises(ValueError, match="independently reviewed"):
        await command.run(args)
    assert not args.output.exists()


@pytest.mark.anyio
async def test_real_handler_receives_request_only_and_shared_ledger_settles(tmp_path, monkeypatch):
    cases, labels, review = reviewed_packet(tmp_path)
    submitted = []
    args = arguments(
        tmp_path,
        routing_dry_run=False,
        routing_label_packet=labels,
        routing_calibration_review=review,
    )

    @asynccontextmanager
    async def backend_client(url, key):
        def respond(request):
            submitted.append(request)
            assert json.loads(args.output.read_text())["budget"]["reserved"] >= 0.0008
            return httpx.Response(
                200,
                json={
                    "schema_version": 1,
                    "routing_version": "workflow-v1",
                    "outcome": "recommended",
                    "workflow": "mmm",
                    "confidence": 0.96,
                    "model": "gpt-6-luna",
                    "input_tokens": 100,
                },
            )

        backend = SimbaAPIClient(url, key)
        backend._client = httpx.AsyncClient(
            base_url=url, headers=backend._headers, transport=httpx.MockTransport(respond)
        )
        try:
            yield backend
        finally:
            await backend.close()

    monkeypatch.setenv("SIMBA_ROUTING_EVAL_API_KEY", "synthetic-backend")
    monkeypatch.setattr(command, "routing_backend_client", backend_client)
    waits = []

    async def no_wait(seconds):
        waits.append(seconds)

    monkeypatch.setattr(command.asyncio, "sleep", no_wait)
    await command.run(args)
    report = json.loads(args.output.read_text())
    assert report["summary"]["counts"] == {"PASS": 2}
    assert report["summary"]["acceptance"] == "NOT_ESTABLISHED"
    assert report["budget"]["charged"] == pytest.approx(0.00002)
    assert report["budget"]["reserved"] == 0
    assert waits == [6.1]
    assert [json.loads(request.content) for request in submitted] == [
        {"schema_version": 1, "request": case.request} for case in cases
    ]
    assert all(
        request.headers["Authorization"] == "Bearer synthetic-backend" for request in submitted
    )
    assert all("synthetic-test-reviewer" not in request.content.decode() for request in submitted)
    assert "synthetic-backend" not in args.output.read_text()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "fault", ["packet_hash", "reviewer", "grader_version", "passed", "samples"]
)
async def test_unbound_review_or_repetitions_fail_before_admission(tmp_path, monkeypatch, fault):
    _, labels, review = reviewed_packet(tmp_path)
    args = arguments(
        tmp_path,
        routing_dry_run=False,
        routing_label_packet=labels,
        routing_calibration_review=review,
    )
    changed = json.loads(review.read_text())
    if fault == "packet_hash":
        changed["packet_sha256"] = "0" * 64
    elif fault == "reviewer":
        changed["reviewer"] = development_cases()[0].author
    elif fault == "grader_version":
        changed["grader_version"] = "unknown"
    elif fault == "passed":
        changed["passed"] = 1
    else:
        args.samples = 2
    review.write_text(json.dumps(changed))
    monkeypatch.setenv("SIMBA_ROUTING_EVAL_API_KEY", "synthetic-backend")
    with pytest.raises(ValueError):
        await command.run(args)
    assert not args.output.exists()


@pytest.mark.anyio
async def test_interrupted_submission_retains_reservation_and_distinguishes_unrun_cases(
    tmp_path, monkeypatch
):
    _, labels, review = reviewed_packet(tmp_path)
    args = arguments(
        tmp_path,
        routing_dry_run=False,
        routing_label_packet=labels,
        routing_calibration_review=review,
    )

    @asynccontextmanager
    async def backend_client(url, key):
        async def interrupted(_):
            import asyncio

            raise asyncio.CancelledError()

        backend = SimbaAPIClient(url, key)
        backend._client = httpx.AsyncClient(
            base_url=url, headers=backend._headers, transport=httpx.MockTransport(interrupted)
        )
        try:
            yield backend
        finally:
            await backend.close()

    import asyncio

    monkeypatch.setenv("SIMBA_ROUTING_EVAL_API_KEY", "synthetic-backend")
    monkeypatch.setattr(command, "routing_backend_client", backend_client)
    with pytest.raises(asyncio.CancelledError):
        await command.run(args)
    report = json.loads(args.output.read_text())
    assert report["status"] == "stopped"
    assert report["summary"]["counts"] == {"EXECUTION_ERROR": 1, "NOT_RUN": 1}
    assert report["budget"]["charged"] == 0 and report["budget"]["reserved"] == pytest.approx(
        0.0008
    )
    assert report["trials"][0]["routing_attempts"][0]["status"] == "interrupted"


@pytest.mark.anyio
async def test_continuation_skips_completed_cases_keeps_unknown_charge_and_checks_prior(
    tmp_path, monkeypatch
):
    import asyncio

    cases, labels, review = reviewed_packet(tmp_path)
    args = arguments(
        tmp_path,
        routing_dry_run=False,
        routing_label_packet=labels,
        routing_calibration_review=review,
    )
    submitted = []

    @asynccontextmanager
    async def backend_client(url, key):
        async def respond(request):
            submitted.append(json.loads(request.content))
            if len(submitted) == 2:
                raise asyncio.CancelledError()
            return httpx.Response(
                200,
                json={
                    "schema_version": 1,
                    "routing_version": "workflow-v1",
                    "outcome": "recommended",
                    "workflow": "mmm",
                    "confidence": 0.96,
                    "model": "gpt-6-luna",
                    "input_tokens": 100,
                },
            )

        backend = SimbaAPIClient(url, key)
        backend._client = httpx.AsyncClient(
            base_url=url, headers=backend._headers, transport=httpx.MockTransport(respond)
        )
        try:
            yield backend
        finally:
            await backend.close()

    async def no_wait(_):
        return None

    monkeypatch.setenv("SIMBA_ROUTING_EVAL_API_KEY", "synthetic-backend")
    monkeypatch.setattr(command, "routing_backend_client", backend_client)
    monkeypatch.setattr(command.asyncio, "sleep", no_wait)
    with pytest.raises(asyncio.CancelledError):
        await command.run(args)
    original = args.output.read_bytes()
    previous = json.loads(original)
    transition = tmp_path / "transition.json"
    transition.write_text(
        json.dumps(
            {
                "verified": True,
                "rationale": "Mechanical unchanged-source fixture only",
                "previous_report_sha256": hashlib.sha256(original).hexdigest(),
                "previous_source_sha256": previous["frozen"]["source_sha256"],
                "current_source_sha256": source_fingerprint(),
            }
        )
    )
    args.continue_from = args.output
    args.continuation_review = transition
    args.output = tmp_path / "continued.json"
    with pytest.raises(ValueError, match="lost spending"):
        await command.run(args)
    assert len(submitted) == 2 and not args.output.exists()
    args.prior_usd = sum(previous["budget"][key] for key in ("prior", "charged", "reserved"))
    assert args.prior_usd == pytest.approx(0.00081)
    await command.run(args)
    resumed = json.loads(args.output.read_text())
    assert submitted == [
        {"schema_version": 1, "request": cases[index].request} for index in (0, 1, 1)
    ]
    assert resumed["summary"]["counts"] == {"PASS": 2}
    assert resumed["attempt_score_counts"] == {"PASS": 2, "EXECUTION_ERROR": 1}
    assert len(resumed["trials"][1]["routing_attempts"]) == 2
    assert resumed["trials"][1]["routing_attempts"][0]["cost_usd"] is None
    assert resumed["budget"]["prior"] == args.prior_usd
    assert resumed["budget"]["charged"] == pytest.approx(0.00001)
    assert args.continue_from.read_bytes() == original
