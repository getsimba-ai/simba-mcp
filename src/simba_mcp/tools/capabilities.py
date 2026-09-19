"""Read capability declarations from the caller's connected backend."""

from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations

from ..auth import _client
from ..runtime import AppContext
from ..schemas.discovery import CapabilityReport


async def get_capabilities(ctx: Context[AppContext, Any]) -> CapabilityReport:
    """Discover backend-advertised model capabilities before configuring a recipe.

    Reads the authenticated canonical schema; does not probe writes or fit models.
    Missing declarations mean unknown, not unsupported. This is feature discovery,
    not proof of this caller's permission, subscription allowance or scientific validity.
    Consult get_data_schema for the complete data contract. No per-caller caching.
    """
    schema = await _client(ctx).get_schema()
    categories = ["model_families", "transformations", "priors", "control_priors", "workflows"]
    if (
        not isinstance(schema, dict)
        or schema.get("error")
        or schema.get("_status_code", 200) >= 400
    ):
        return CapabilityReport(
            status="unavailable",
            unknown=categories,
            guidance="Resolve the backend error before choosing model capabilities.",
            backend_error=schema
            if isinstance(schema, dict)
            else {"error": "Invalid schema response"},
        )
    advertised = schema.get("x-simba-model-capabilities")
    if not isinstance(advertised, dict):
        advertised = {}
    return CapabilityReport(
        status="reported" if advertised else "unadvertised",
        advertised=advertised,
        unknown=[name for name in categories if name not in advertised],
        guidance="Use only explicit backend declarations as evidence of support. Nested control_priors.transforms apply only to controls. Missing categories require backend documentation or an upgrade; do not infer support from MCP tool availability.",
    )


def register(mcp: MCPServer) -> None:
    mcp.tool(
        title="Discover Simba capabilities",
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )(get_capabilities)
