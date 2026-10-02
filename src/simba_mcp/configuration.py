"""Shipped server configuration: inventory, precedence and a non-sensitive report.

    python -m simba_mcp.configuration
    python -m simba_mcp.configuration --check

The report uses the same parsers as server startup. It never prints credentials,
raw policy text or rejected values. It is not an MCP tool and does not change
the running server.
"""

import argparse
import ast
import inspect
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .api_client import DEFAULT_TIMEOUT, MAX_RETRIES, effective_response_limits
from .auth import local_files_effective
from .oauth import CACHE_TTL_SECONDS, oauth_enabled, public_url
from .profiles import PROFILE_NAMES, validate_profile
from .request_budget import policy_from_json
from .runtime import (
    DESCRIPTION_MODES,  # noqa: F401 - preserve the public configuration constant
    MAX_REQUEST_BODY_BYTES,
    MAX_UPLOAD_BYTES,
    _response_byte_limit,
    description_mode,
)

TRANSPORTS = ("stdio", "streamable-http", "sse")
METRICS_VALUE = "stderr"
DOCS = Path(__file__).resolve().parents[2] / "docs" / "configuration.md"
PACKAGE = Path(__file__).resolve().parent
PACKAGED_DOCS = PACKAGE / "configuration.md"

_ENV_NAME = re.compile(r"""["']((?:SIMBA_|MCP_)[A-Z0-9_]+)["']""")
_FLAG = re.compile(r"""add_argument\(\s*["'](--[a-z0-9-]+)["']""")


class ConfigurationError(ValueError):
    """A supplied control is invalid. The message names the control, not the value."""


def controls():
    """Every shipped server control. Evaluation and benchmark commands are separate."""
    return (
        {
            "identity": "SIMBA_API_URL",
            "kind": "environment",
            "owner_module": "simba_mcp.runtime",
            "purpose": "Backend base URL for the shared client.",
            "owner": "operator",
            "scope": "process",
            "state": "default http://localhost:5005",
            "lifecycle": "Read at lifespan start. Restart to change. A development .env configures only the process that loads it.",
            "precedence": "Environment, otherwise the default. Userinfo, query and fragment are credentials, not configuration to display.",
            "authority": "Operator. Callers cannot change the shared client URL.",
            "evidence": "Existing local default. No production URL is selected by this inventory.",
        },
        {
            "identity": "SIMBA_API_KEY",
            "kind": "environment",
            "owner_module": "simba_mcp.runtime",
            "purpose": "Operator key for stdio. Unused on HTTP/SSE, where each caller supplies a bearer.",
            "owner": "operator for stdio; authenticated caller for HTTP/SSE",
            "scope": "process on stdio; request on HTTP/SSE",
            "state": "absent until set; never a shared fallback on HTTP/SSE",
            "lifecycle": "Restart stdio after changing it. Hosted callers rotate their own bearer in the MCP host.",
            "precedence": "HTTP/SSE ignores it even when set. Stdio uses it. Absence is reported, never the value.",
            "authority": "Does not grant a caller another caller's identity.",
            "evidence": "Bring-your-own-key boundary. Inventory records presence only.",
        },
        {
            "identity": "SIMBA_API_REQUEST_POLICY_JSON",
            "kind": "environment",
            "owner_module": "simba_mcp.request_budget",
            "purpose": "Optional deadlines and admission for the shared client.",
            "owner": "operator",
            "scope": "process",
            "state": "disabled unless set; JSON false also disables it",
            "lifecycle": "Restart to change. Rollback is unsetting it.",
            "precedence": "Invalid JSON or fields fail startup. No numeric recommendation is implied by the parser.",
            "authority": "Operator only. Agent arguments cannot raise these ceilings.",
            "evidence": "Unset keeps the existing client timeout and retry loop and adds no admission.",
        },
        {
            "identity": "SIMBA_API_MAX_ENCODED_BYTES",
            "kind": "environment",
            "owner_module": "simba_mcp.runtime",
            "purpose": "Optional encoded response ceiling.",
            "owner": "operator",
            "scope": "process",
            "state": "unset inherits the decoded ceiling; neither set means no local ceiling",
            "lifecycle": "Restart to change. Rollback is unsetting it.",
            "precedence": "A positive integer, or unset. A caller max_response_bytes cannot raise it.",
            "authority": "Operator ceiling. It bounds the backend download, not MCP display alone.",
            "evidence": "Opt-in until a measured deployment selects a number.",
        },
        {
            "identity": "SIMBA_API_MAX_DECODED_BYTES",
            "kind": "environment",
            "owner_module": "simba_mcp.runtime",
            "purpose": "Optional decoded response ceiling.",
            "owner": "operator",
            "scope": "process",
            "state": "unset inherits the encoded ceiling; neither set means no local ceiling",
            "lifecycle": "Restart to change. Rollback is unsetting it.",
            "precedence": "A positive integer, or unset. Either byte setting fills the other when only one is set.",
            "authority": "Operator ceiling.",
            "evidence": "Opt-in until a measured deployment selects a number.",
        },
        {
            "identity": "SIMBA_TOOL_DESCRIPTIONS",
            "kind": "environment",
            "owner_module": "simba_mcp.server",
            "purpose": "Choose legacy or compact tool descriptions.",
            "owner": "operator",
            "scope": "process catalogue",
            "state": "default legacy; compact is opt-in",
            "lifecycle": "Read at server construction. Reconnect after changing it.",
            "precedence": "legacy or compact. No other value is accepted.",
            "authority": "Operator. Compact text does not grant tools or permissions.",
            "evidence": "No measured production default replaces legacy.",
        },
        {
            "identity": "SIMBA_TOOL_PROFILE",
            "kind": "environment",
            "owner_module": "simba_mcp.server",
            "purpose": "Fixed tool view. full and data_scientist expose the canonical catalogue.",
            "owner": "operator",
            "scope": "process catalogue",
            "state": "default full",
            "lifecycle": "Read at server construction unless --profile is passed. Reconnect after changing it.",
            "precedence": "--profile overrides a valid environment value. Invalid or empty environment values fail server import before the override.",
            "authority": "A profile hides tools. It does not grant backend permissions.",
            "evidence": "Shipped profiles are full, data_scientist, marketer and reviewer.",
        },
        {
            "identity": "--profile",
            "kind": "argument",
            "owner_module": "simba_mcp.__main__",
            "purpose": "Launch-time override of SIMBA_TOOL_PROFILE.",
            "owner": "operator",
            "scope": "process",
            "state": "optional; absence leaves the environment or default",
            "lifecycle": "Applies to that CLI process only.",
            "precedence": "Wins over SIMBA_TOOL_PROFILE. Ignored by uvicorn simba_mcp.server:app.",
            "authority": "Operator launch configuration.",
            "evidence": "Same names as the environment variable.",
        },
        {
            "identity": "--transport",
            "kind": "argument",
            "owner_module": "simba_mcp.__main__",
            "purpose": "stdio, streamable-http or sse.",
            "owner": "operator",
            "scope": "process",
            "state": "default stdio",
            "lifecycle": "Launch argument. HTTP and SSE mark the process as a network transport.",
            "precedence": "uvicorn simba_mcp.server:app is a separate ASGI path and is always HTTP mode.",
            "authority": "Operator. Agents cannot switch transport.",
            "evidence": "stdio is the local default. Hosted deployment chooses a network transport explicitly.",
        },
        {
            "identity": "--host",
            "kind": "argument",
            "owner_module": "simba_mcp.__main__",
            "purpose": "Bind host for the CLI network transports.",
            "owner": "operator",
            "scope": "process",
            "state": "default 0.0.0.0; unused for stdio",
            "lifecycle": "Launch argument. The ASGI helper also passes 0.0.0.0 to disable localhost DNS-rebinding protection behind a proxy.",
            "precedence": "Does not apply to stdio or to the process manager's uvicorn bind.",
            "authority": "Operator.",
            "evidence": "Existing CLI default.",
        },
        {
            "identity": "--port",
            "kind": "argument",
            "owner_module": "simba_mcp.__main__",
            "purpose": "Bind port for the CLI network transports.",
            "owner": "operator",
            "scope": "process",
            "state": "default 8100; unused for stdio",
            "lifecycle": "Launch argument. Uvicorn's own port is outside this flag.",
            "precedence": "CLI only.",
            "authority": "Operator.",
            "evidence": "Existing CLI default.",
        },
        {
            "identity": "SIMBA_MCP_ALLOW_LOCAL_FILES",
            "kind": "environment",
            "owner_module": "simba_mcp.auth",
            "purpose": "Allow csv_path to read the server host filesystem.",
            "owner": "operator",
            "scope": "process",
            "state": "stdio allows by default; HTTP/SSE denies unless explicitly enabled",
            "lifecycle": "Read on each local-file check. Restart workers that cached an old environment.",
            "precedence": "1, true or yes allows. 0, false or no denies. Any other value follows the transport default.",
            "authority": "Operator. A caller cannot enable the server filesystem from a tool argument.",
            "evidence": "Network default is deny because the path is the server's, not the caller's.",
        },
        {
            "identity": "SIMBA_MCP_METRICS",
            "kind": "environment",
            "owner_module": "simba_mcp.telemetry",
            "purpose": "Write structured metrics to stderr.",
            "owner": "operator",
            "scope": "process, with a task-local override for embeddings and benchmarks",
            "state": "off unless the value is exactly stderr",
            "lifecycle": "Read when an event is emitted. Rollback is unsetting it.",
            "precedence": "Only the exact value stderr enables the process sink. A task-local override wins for that task.",
            "authority": "Operator. Events must not include credentials.",
            "evidence": "Opt-in diagnostic. 1 and true do not enable it.",
        },
        {
            "identity": "MCP_OAUTH_ENABLED",
            "kind": "environment",
            "owner_module": "simba_mcp.oauth",
            "purpose": "Optional OAuth resource-server mode.",
            "owner": "operator",
            "scope": "process",
            "state": "off unless 1, true or yes",
            "lifecycle": "Read at server construction. Restart to change. Off leaves bring-your-own-key unchanged.",
            "precedence": "Any other value leaves it off. The server holds no OAuth client secret.",
            "authority": "Operator. Enabling it does not issue tokens.",
            "evidence": "Shipped off by default. Not a universal host feature.",
        },
        {
            "identity": "SIMBA_PUBLIC_URL",
            "kind": "environment",
            "owner_module": "simba_mcp.oauth",
            "purpose": "Issuer and resource base when OAuth mode is on.",
            "owner": "operator",
            "scope": "process",
            "state": "default http://localhost:8100; unused while OAuth is off",
            "lifecycle": "Restart after changing it. Rollback with OAuth mode.",
            "precedence": "Ignored for authentication while MCP_OAUTH_ENABLED is off.",
            "authority": "Operator. It is a public URL, not a secret.",
            "evidence": "Required for a real hosted issuer. The localhost default is not a hosted recommendation.",
        },
        {
            "identity": "MAX_UPLOAD_BYTES",
            "kind": "constant",
            "owner_module": "simba_mcp.runtime",
            "purpose": "CSV ingest ceiling.",
            "owner": "maintainer",
            "scope": "build",
            "state": f"{MAX_UPLOAD_BYTES} bytes",
            "lifecycle": "Code change and release. Not an environment variable.",
            "precedence": "Fixed. Proxy limits must allow at least the transport cap.",
            "authority": "Server-enforced.",
            "evidence": "Existing 10 MiB ingest limit.",
        },
        {
            "identity": "MAX_REQUEST_BODY_BYTES",
            "kind": "constant",
            "owner_module": "simba_mcp.runtime",
            "purpose": "MCP request body cap for CLI HTTP/SSE and the ASGI app.",
            "owner": "maintainer",
            "scope": "build",
            "state": f"{MAX_REQUEST_BODY_BYTES} bytes",
            "lifecycle": "Code change and release.",
            "precedence": "Fixed. Front proxies must allow at least this size or they reject the upload first.",
            "authority": "Server-enforced.",
            "evidence": "12 MiB accommodates the 10 MiB ingest limit.",
        },
        {
            "identity": "DEFAULT_TIMEOUT",
            "kind": "constant",
            "owner_module": "simba_mcp.api_client",
            "purpose": "Client timeout when request policy is disabled.",
            "owner": "maintainer",
            "scope": "build",
            "state": f"{DEFAULT_TIMEOUT} seconds; up to {MAX_RETRIES} read attempts",
            "lifecycle": "Code change and release. Not selected as a new production policy.",
            "precedence": "Used only while SIMBA_API_REQUEST_POLICY_JSON is disabled.",
            "authority": "Server-enforced. Writes are not retried.",
            "evidence": "Existing client behaviour, retained by leaving policy unset.",
        },
    )


def referenced_environment_names(root: Path | None = None) -> set[str]:
    """Quoted SIMBA_ and MCP_ names in server code, excluding evaluation commands."""
    root = root or PACKAGE
    names: set[str] = set()
    for path in root.rglob("*.py"):
        if "evaluation" in path.parts:
            continue
        names.update(_ENV_NAME.findall(path.read_text(encoding="utf-8")))
    return names


def command_flags(path: Path | None = None) -> set[str]:
    path = path or PACKAGE / "__main__.py"
    return set(_FLAG.findall(path.read_text(encoding="utf-8")))


def dynamic_environment_lookups(root: Path | None = None) -> list[str]:
    """os.environ lookups whose variable name is not a literal."""
    root = root or PACKAGE
    found = []
    for path in root.rglob("*.py"):
        if "evaluation" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr != "get":
                continue
            value = func.value
            if not isinstance(value, ast.Attribute) or value.attr != "environ":
                continue
            if not node.args or isinstance(node.args[0], ast.Constant):
                continue
            found.append(f"{path.name}:{node.lineno}")
    return found


def _reject(identity: str) -> ConfigurationError:
    return ConfigurationError(f"{identity} is invalid")


def _public_base(value: str) -> tuple[str, bool]:
    parts = urlsplit(value)
    sensitive = bool(parts.username or parts.password or parts.query or parts.fragment)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", "")), sensitive


def _policy_report(raw: str | None) -> dict:
    if raw is None or not raw.strip():
        return {"enabled": False, "source": "unset", "fallback_timeout_seconds": DEFAULT_TIMEOUT}
    try:
        policy = policy_from_json(raw)
    except ValueError as exc:
        raise _reject("SIMBA_API_REQUEST_POLICY_JSON") from exc
    if policy is None:
        return {"enabled": False, "source": "disabled", "fallback_timeout_seconds": DEFAULT_TIMEOUT}
    return {
        "enabled": True,
        "source": "environment",
        "total_seconds": policy.total_seconds,
        "connect_seconds": policy.connect_seconds,
        "read_seconds": policy.read_seconds,
        "write_seconds": policy.write_seconds,
        "pool_seconds": policy.pool_seconds,
        "max_active": policy.max_active,
        "max_active_per_caller": policy.max_active_per_caller,
        "max_queued": policy.max_queued,
        "max_queued_per_caller": policy.max_queued_per_caller,
        "operation_seconds": dict(policy.operation_seconds),
    }


def _limit_report(name: str) -> dict:
    try:
        value = _response_byte_limit(name)
    except ValueError as exc:
        raise _reject(name) from exc
    return {"value": value, "source": "unset" if value is None else "environment"}


def effective_configuration(argv: argparse.Namespace | None = None) -> dict:
    """Resolve one launch combination. Does not open a connection or print secrets."""
    args = argv or argparse.Namespace(
        transport="stdio", host="0.0.0.0", port=8100, profile=None, deployment="cli"
    )
    if args.deployment not in ("cli", "asgi"):
        raise _reject("--deployment")
    if args.transport not in TRANSPORTS:
        raise _reject("--transport")
    serving_http = args.deployment == "asgi" or args.transport != "stdio"
    warnings = []

    profile_env = os.environ.get("SIMBA_TOOL_PROFILE", "full")
    try:
        # The server singleton validates the environment before the CLI override.
        validate_profile(profile_env)
        profile = validate_profile(args.profile) if args.profile is not None else profile_env
    except ValueError as exc:
        raise _reject("SIMBA_TOOL_PROFILE") from exc
    profile_source = (
        "argument"
        if args.profile is not None
        else "environment"
        if "SIMBA_TOOL_PROFILE" in os.environ
        else "default"
    )

    description = os.environ.get("SIMBA_TOOL_DESCRIPTIONS", "legacy")
    description_source = "default" if "SIMBA_TOOL_DESCRIPTIONS" not in os.environ else "environment"
    try:
        description_mode(description)
    except ValueError as exc:
        raise _reject("SIMBA_TOOL_DESCRIPTIONS") from exc

    api_url_raw = os.environ.get("SIMBA_API_URL", "http://localhost:5005")
    api_url, api_url_sensitive = _public_base(api_url_raw)
    if api_url_sensitive:
        warnings.append("SIMBA_API_URL contains credentials or a query; those parts are omitted")
    key_configured = bool(os.environ.get("SIMBA_API_KEY", "").strip())
    if serving_http:
        key = {"configured": key_configured, "used": False, "reason": "ignored_in_http_mode"}
    else:
        key = {
            "configured": key_configured,
            "used": key_configured,
            "reason": "stdio" if key_configured else "absent",
        }

    files_raw = os.environ.get("SIMBA_MCP_ALLOW_LOCAL_FILES")
    files_allowed, files_source = local_files_effective(files_raw, serving_http)
    if files_raw and files_raw.strip().lower() not in {"1", "true", "yes", "0", "false", "no"}:
        warnings.append(
            "SIMBA_MCP_ALLOW_LOCAL_FILES is unrecognised and follows the transport default"
        )

    metrics_raw = os.environ.get("SIMBA_MCP_METRICS")
    metrics_enabled = metrics_raw == METRICS_VALUE
    if metrics_raw not in (None, "", METRICS_VALUE):
        warnings.append("SIMBA_MCP_METRICS enables output only when the value is exactly stderr")

    oauth = oauth_enabled()
    oauth_raw = os.environ.get("MCP_OAUTH_ENABLED", "")
    if oauth_raw.strip() and not oauth and oauth_raw.strip().lower() not in {"0", "false", "no"}:
        warnings.append("MCP_OAUTH_ENABLED is unrecognised and leaves OAuth off")
    public_raw = public_url() if oauth or os.environ.get("SIMBA_PUBLIC_URL") else None
    public = None
    if public_raw is not None:
        public, public_sensitive = _public_base(public_raw)
        if public_sensitive:
            warnings.append(
                "SIMBA_PUBLIC_URL contains credentials or a query; those parts are omitted"
            )
        if not oauth:
            warnings.append("SIMBA_PUBLIC_URL is unused while MCP_OAUTH_ENABLED is off")

    encoded = _limit_report("SIMBA_API_MAX_ENCODED_BYTES")
    decoded = _limit_report("SIMBA_API_MAX_DECODED_BYTES")
    limits = effective_response_limits(encoded["value"], decoded["value"])
    for item, value, other in (
        (encoded, limits[0], "SIMBA_API_MAX_DECODED_BYTES"),
        (decoded, limits[1], "SIMBA_API_MAX_ENCODED_BYTES"),
    ):
        if item["value"] is None and value is not None:
            item.update(value=value, source="fallback", inherited_from=other)
    network = serving_http and args.deployment == "cli"
    return {
        "deployment": args.deployment,
        "transport": {
            "value": "asgi-streamable-http" if args.deployment == "asgi" else args.transport,
            "source": "asgi" if args.deployment == "asgi" else "argument",
            "serving_http": serving_http,
        },
        "bind": {
            "host": args.host if network else None,
            "port": args.port if network else None,
            "source": "argument" if network else "not-applicable",
        },
        "profile": {"value": profile, "source": profile_source},
        "description_mode": {"value": description, "source": description_source},
        "api_url": {
            "value": api_url,
            "source": "environment" if "SIMBA_API_URL" in os.environ else "default",
            "credential_omitted": api_url_sensitive,
        },
        "api_key": key,
        "request_policy": _policy_report(os.environ.get("SIMBA_API_REQUEST_POLICY_JSON")),
        "max_encoded_bytes": encoded,
        "max_decoded_bytes": decoded,
        "local_files": {"allowed": files_allowed, "source": files_source},
        "metrics": {
            "enabled": metrics_enabled,
            "source": "environment" if metrics_enabled else "off",
        },
        "oauth": {"enabled": oauth, "public_url": public if oauth else None},
        "ceilings": {
            "max_upload_bytes": MAX_UPLOAD_BYTES,
            "max_request_body_bytes": MAX_REQUEST_BODY_BYTES,
            "fallback_timeout_seconds": DEFAULT_TIMEOUT,
            "oauth_positive_cache_seconds": CACHE_TTL_SECONDS,
        },
        "warnings": warnings,
    }


def per_call_options() -> list[str]:
    from .tools.results import get_model_results

    return [name for name in inspect.signature(get_model_results).parameters if name != "ctx"]


def render_docs() -> str:
    rows = [
        "| Identity | Kind | Owner module | Owner | Scope | State |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in controls():
        rows.append(
            f"| `{row['identity']}` | {row['kind']} | `{row['owner_module']}` | {row['owner']} | {row['scope']} | {row['state']} |"
        )
    details = []
    for row in controls():
        details.extend(
            [
                f"### `{row['identity']}`",
                "",
                f"- Purpose: {row['purpose']}",
                f"- Lifecycle: {row['lifecycle']}",
                f"- Resolution: {row['precedence']}",
                f"- Authority: {row['authority']}",
                f"- Evidence: {row['evidence']}",
                "",
            ]
        )
    options = ", ".join(f"`{name}`" for name in per_call_options())
    return "\n".join(
        [
            "# Server configuration",
            "",
            "Generated from `simba_mcp.configuration`. Do not edit this page by hand.",
            "Check it with `python -m simba_mcp.configuration --check`.",
            "The installed wheel includes this reference. Source checkouts also check docs/configuration.md.",
            "",
            "Runtime owns resolution. This page and `python -m simba_mcp.configuration`",
            "report the same controls without becoming a second settings framework or an MCP tool.",
            "",
            "## Product decision",
            "",
            "This release does not add an application settings UI. Connection credentials",
            "stay in the MCP host configuration. Operator ceilings stay in the server process",
            "environment or launch arguments. Agents choose documented per-call tool arguments",
            "and cannot raise server ceilings, change the shared catalogue or expand permissions.",
            "A UI is not required for this release. Concise-versus-detailed preferences remain",
            "unimplemented proposals, not settings.",
            "",
            "A development `.env` configures only the process that loads it. It does not",
            "configure a remote server, a hosted MCP endpoint or every client.",
            "",
            "## How to inspect",
            "",
            "```bash",
            "python -m simba_mcp.configuration",
            "python -m simba_mcp.configuration --deployment asgi",
            "```",
            "",
            "The JSON report omits credential values, URL userinfo, queries and rejected",
            "inputs. Exit code 2 means a control would fail server startup. Warnings do not",
            "change the effective value. This check does not connect to the backend and does",
            "not prove a hosted deployment.",
            "",
            "## Precedence",
            "",
            "1. Server constants and operator process settings bound every caller.",
            "2. `--profile` overrides `SIMBA_TOOL_PROFILE` for the CLI process only.",
            "3. HTTP/SSE ignores `SIMBA_API_KEY` and uses the request bearer.",
            "4. Per-call arguments can select evidence or impose a tighter content cap.",
            "   They cannot raise byte ceilings, disable admission or enable server filesystem reads.",
            "5. Backend authorisation remains definitive.",
            "",
            "## Examples, not measured production defaults",
            "",
            "Local stdio: set the backend URL and operator key. Leave description mode, profile,",
            "request policy and byte ceilings at their defaults unless the operator has a measured",
            "reason to change them. The localhost URL is a development default, not a hosted recommendation.",
            "",
            "Hosted HTTP: launch `streamable-http` or `uvicorn simba_mcp.server:app`. Callers",
            "authenticate with their own bearer. The operator key is unused. Local files stay",
            "denied unless the operator explicitly enables them. OAuth mode stays off unless",
            "this deployment serves protected-resource metadata. Do not copy a numeric request",
            "policy from this document; none is recommended here.",
            "",
            "## Inventory",
            "",
            *rows,
            "",
            *details,
            "## Per-call result arguments",
            "",
            f"`get_model_results` accepts {options}. `ctx` is framework context, not a caller setting.",
            "`max_response_bytes`, when present, rejects an oversize MCP payload. It does not",
            "limit the backend download and cannot raise `SIMBA_API_MAX_ENCODED_BYTES` or",
            "`SIMBA_API_MAX_DECODED_BYTES`. Channel, grid, section and window arguments select",
            "evidence. They are not operator configuration and they do not grant missing sections.",
            "",
            "## Out of this inventory",
            "",
            "Evaluation, benchmark and documentation commands have their own arguments and",
            "provider credentials. Those credentials are not server configuration and are not",
            "printed by this report. Guidance installation is a client workflow, not a server flag.",
            "",
        ]
    )


def coverage_errors() -> list[str]:
    identities = {row["identity"] for row in controls()}
    errors = []
    missing = sorted(name for name in referenced_environment_names() if name not in identities)
    if missing:
        errors.append("environment names missing from the inventory: " + ", ".join(missing))
    flags = sorted(flag for flag in command_flags() if flag not in identities)
    if flags:
        errors.append("CLI flags missing from the inventory: " + ", ".join(flags))
    dynamic = dynamic_environment_lookups()
    allowed_dynamic = {"runtime.py"}
    unexpected = [item for item in dynamic if item.split(":", 1)[0] not in allowed_dynamic]
    if unexpected:
        errors.append("unexpected dynamic environment lookups: " + ", ".join(unexpected))
    if (
        not PACKAGED_DOCS.is_file()
        or PACKAGED_DOCS.read_text(encoding="utf-8") != render_docs()
        or (
            DOCS.parent.is_dir()
            and (not DOCS.is_file() or DOCS.read_text(encoding="utf-8") != render_docs())
        )
    ):
        errors.append(
            "docs/configuration.md is stale; run python -m simba_mcp.configuration --write-docs"
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transport", choices=TRANSPORTS, default="stdio")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--profile", choices=PROFILE_NAMES)
    parser.add_argument("--deployment", choices=("cli", "asgi"), default="cli")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write-docs", action="store_true")
    args = parser.parse_args(argv)
    if args.write_docs:
        PACKAGED_DOCS.write_text(render_docs(), encoding="utf-8", newline="\n")
        if DOCS.parent.is_dir():
            DOCS.write_text(render_docs(), encoding="utf-8", newline="\n")
    if args.check or args.write_docs:
        errors = coverage_errors()
        if errors:
            print("\n".join(errors))
            return 1
        if args.check:
            print("Configuration inventory matches code and docs")
        if not args.check:
            return 0
        return 0
    try:
        print(json.dumps(effective_configuration(args), indent=2, sort_keys=True))
    except ConfigurationError as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
