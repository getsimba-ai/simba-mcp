"""Packaged, dependency-free MCP Apps resource registration."""

from importlib.resources import files

from mcp.server.apps import Apps, ResourceCsp

RESOURCE_URI = "ui://simba/charts.html"
VISUAL_TOOLS = frozenset(
    {"show_response_curves", "show_decomposition", "show_optimizer_allocation"}
)


def chart_apps() -> Apps:
    apps = Apps()
    apps.add_html_resource(
        RESOURCE_URI,
        files("simba_mcp").joinpath("ui/charts.html").read_text(encoding="utf-8"),
        title="Simba result charts",
        description="Read-only charts of served results, with exact-value tables.",
        csp=ResourceCsp(),
        prefers_border=True,
    )
    return apps
