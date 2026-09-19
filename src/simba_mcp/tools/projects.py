"""Projects tools backed by the shared Simba API."""

from typing import Any

from mcp.server.mcpserver import Context

from ..auth import _client
from ..runtime import AppContext


async def list_projects(
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """List the projects (the app's model folders) you can file models into.

    Returns owned and team-shared projects: per project {id, name,
    is_default, shared_with_team_id, model_count} — team-shared folders
    carry "shared": true, and model_count counts SAVED models (the set the
    app's model list shows). Use the ids with save_model(project_id=...)
    and rename_project. There is deliberately no delete over the API — use
    the app to delete a project.
    """
    return await _client(ctx).list_projects()


async def create_project(
    name: str,
    team_id: int | None = None,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Create a named project (model folder) to file models into.

    Names are sanitized the same way model names are (non-empty after
    HTML sanitization).

    Args:
        name: Display name for the new project.
        team_id: Optional team to share the project with; must be a team
            you belong to (403 otherwise, 404 for an unknown team).

    Returns the created project (201) including its id — pass that to
    save_model(project_id=...).
    """
    return await _client(ctx).create_project(name, team_id=team_id)


async def rename_project(
    project_id: int,
    name: str,
    ctx: Context[AppContext, Any] = None,
) -> dict:
    """Rename a project you OWN.

    Team members can file models into a shared folder but not rename it
    (owner-only; 404 for a project you don't own). Renaming your default
    folder is safe: it keeps receiving unqualified saves under its new name.

    Args:
        project_id: Id of the project to rename (see list_projects).
        name: New display name.
    """
    return await _client(ctx).rename_project(project_id, name)
