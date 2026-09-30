"""Bounded local guidance lookup. No backend state or authorisation decisions."""

from typing import Any

from simba_mcp.guidance import read_guidance


async def get_workflow_guidance(
    topic: str = "index", section: str = "entrypoint"
) -> dict[str, Any]:
    """Read versioned Simba workflow guidance when native Skills are unavailable.

    Use index only when the required topic/section is unknown.
    Topics: mmm, results, priors, optimiser, studies, var. The default section is
    entrypoint; it names detailed sections and when they are needed. Arguments are
    identifiers, never paths. Returns a complete section within a 24,000-byte structured-payload
    limit or a refusal, never truncated instructions. This local read makes no
    backend request. Guidance does not authorise writes or replace validation.
    Reuse relevant guidance already supplied in context; request only missing sections.
    """
    return read_guidance(topic, section)
