"""Projects tools backed by the Simba API."""

from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations

from ..auth import _client
from ..runtime import AppContext


async def list_projects(
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """List the projects (the app's model folders) you can file models into.

    Returns owned and team-shared projects: per project {id, name,
    is_default, shared_with_team_id, model_count} â€” team-shared folders
    carry "shared": true, and model_count counts SAVED models (the set the
    app's model list shows). Use the ids with save_model(project_id=...)
    and rename_project. There is deliberately no delete over the API â€” use
    the app to delete a project.
    """
    return await _client(ctx).list_projects()


async def create_project(
    name: str,
    team_id: int | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Create a named project (model folder) to file models into.

    Names are sanitized the same way model names are (non-empty after
    HTML sanitization).

    Args:
        name: Display name for the new project.
        team_id: Optional team to share the project with; must be a team
            you belong to (403 otherwise, 404 for an unknown team).

    Returns the created project (201) including its id â€” pass that to
    save_model(project_id=...).
    """
    return await _client(ctx).create_project(name, team_id=team_id)


async def rename_project(
    project_id: int,
    name: str,
    ctx: Context[AppContext, Any] = None,
) -> dict[str, Any]:
    """Rename a project you OWN.

    Team members can file models into a shared folder but not rename it
    (owner-only; 404 for a project you don't own). Renaming your default
    folder is safe: it keeps receiving unqualified saves under its new name.

    Args:
        project_id: Id of the project to rename (see list_projects).
        name: New display name.
    """
    return await _client(ctx).rename_project(project_id, name)


def register(mcp: MCPServer) -> None:
    mcp.tool(
        title="List projects",
        annotations=ToolAnnotations(
            read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True
        ),
    )(list_projects)
    mcp.tool(
        title="Create project",
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        ),
    )(create_project)
    mcp.tool(
        title="Rename project",
        annotations=ToolAnnotations(
            read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=True
        ),
    )(rename_project)
