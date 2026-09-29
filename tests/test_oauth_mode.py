"""Optional OAuth resource-server mode (#59): off by default and byte-identical to today; on,
the SDK serves the protected-resource metadata and 401s without a verified bearer, and the
verifier asks the backend's token-info route with the caller's own bearer."""

import time

import anyio
import httpx
import pytest

from simba_mcp import oauth, runtime
from simba_mcp.oauth import BackendTokenVerifier, server_auth_options

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "t", "version": "0"},
    },
}
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _transport(handler):
    return httpx.MockTransport(handler)


class TestFlagOff:
    def test_no_auth_kwargs_with_the_flag_off(self, monkeypatch):
        monkeypatch.delenv("MCP_OAUTH_ENABLED", raising=False)
        assert server_auth_options("http://backend:5000") == {}

    def test_server_options_are_unchanged(self, monkeypatch):
        monkeypatch.delenv("MCP_OAUTH_ENABLED", raising=False)
        from simba_mcp import server as srv

        instance = srv.create_server("legacy")
        assert instance.settings.auth is None if hasattr(instance, "settings") else True


class TestFlagOn:
    def test_auth_kwargs_name_the_public_url(self, monkeypatch):
        monkeypatch.setenv("MCP_OAUTH_ENABLED", "1")
        monkeypatch.setenv("SIMBA_PUBLIC_URL", "https://demo.example/")
        options = server_auth_options("http://backend:5000")
        assert str(options["auth"].issuer_url).rstrip("/") == "https://demo.example"
        assert str(options["auth"].resource_server_url).rstrip("/") == "https://demo.example/mcp"
        assert options["auth"].required_scopes is None
        assert isinstance(options["token_verifier"], BackendTokenVerifier)

    def test_initialize_is_401_with_resource_metadata_and_the_document_is_served(self, monkeypatch):
        from starlette.testclient import TestClient

        from simba_mcp import server as srv

        monkeypatch.setenv("MCP_OAUTH_ENABLED", "1")
        monkeypatch.setenv("SIMBA_PUBLIC_URL", "https://demo.example")
        monkeypatch.setenv("SIMBA_API_URL", "http://backend:5000")
        monkeypatch.setattr(runtime, "_serving_http", runtime._serving_http)
        app = runtime.create_app(srv.create_server("legacy"))
        with TestClient(app) as client:
            init = client.post("/", json=INIT, headers=HEADERS)
            assert init.status_code == 401
            www = init.headers.get("www-authenticate", "")
            assert (
                "resource_metadata=" in www and "/.well-known/oauth-protected-resource/mcp" in www
            )
            doc = client.get("/.well-known/oauth-protected-resource/mcp")
            assert doc.status_code == 200
            body = doc.json()
            assert body["resource"].rstrip("/") == "https://demo.example/mcp"
            assert [u.rstrip("/") for u in body["authorization_servers"]] == [
                "https://demo.example"
            ]


class TestVerifier:
    def _verifier(self, handler):
        return BackendTokenVerifier(
            "http://backend:5000", client=httpx.AsyncClient(transport=_transport(handler))
        )

    def test_a_live_oauth_token_maps_to_the_principal(self):
        seen = {}

        def handler(request):
            seen["auth"] = request.headers.get("authorization")
            seen["path"] = request.url.path
            return httpx.Response(
                200,
                json={
                    "kind": "oauth",
                    "principal": {"user_id": 7, "email": "a@b"},
                    "client_id": "simba_client_x",
                    "scopes": ["read:models"],
                    "expires_at": "2099-01-01T00:00:00",
                    "resource": "https://demo.example",
                },
            )

        token = anyio.run(self._verifier(handler).verify_token, "simba_at_abc")
        assert seen == {"auth": "Bearer simba_at_abc", "path": "/api/v1/auth/token-info"}
        assert token.client_id == "simba_client_x" and token.scopes == ["read:models"]
        assert (
            token.subject == "7" and token.resource == "https://demo.example" and token.expires_at
        )

    def test_an_api_key_also_verifies(self):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "kind": "api_key",
                    "principal": {"user_id": 7, "email": "a@b"},
                    "key_prefix": "simba_sk_12345678",
                    "scopes": ["ingest"],
                    "expires_at": None,
                },
            )

        token = anyio.run(self._verifier(handler).verify_token, "simba_sk_12345678rest")
        assert (
            token is not None
            and token.client_id == "simba_sk_12345678"
            and token.scopes == ["ingest"]
        )

    def test_positive_answers_are_cached_and_negative_ones_are_not(self):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if request.headers["authorization"].endswith("bad"):
                return httpx.Response(401, json={"error": "invalid_token"})
            return httpx.Response(
                200,
                json={
                    "kind": "oauth",
                    "principal": {"user_id": 1},
                    "client_id": "c",
                    "scopes": [],
                    "expires_at": None,
                },
            )

        verifier = self._verifier(handler)
        assert anyio.run(verifier.verify_token, "simba_at_good") is not None
        assert anyio.run(verifier.verify_token, "simba_at_good") is not None
        assert calls["n"] == 1
        assert anyio.run(verifier.verify_token, "simba_at_bad") is None
        assert anyio.run(verifier.verify_token, "simba_at_bad") is None
        assert calls["n"] == 3
        assert all(len(key) == 64 and "simba_at_" not in key for key in verifier._cache)

    def test_backend_failures_are_a_refusal_not_a_crash(self):
        def five_hundred(request):
            return httpx.Response(503, text="down")

        def boom(request):
            raise httpx.ConnectTimeout("slow")

        assert anyio.run(self._verifier(five_hundred).verify_token, "simba_at_x") is None
        assert anyio.run(self._verifier(boom).verify_token, "simba_at_x") is None
        assert anyio.run(self._verifier(five_hundred).verify_token, "") is None

    def test_cache_never_outlives_the_token(self):
        soon = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + 5))

        def handler(request):
            return httpx.Response(
                200,
                json={
                    "kind": "oauth",
                    "principal": {"user_id": 1},
                    "client_id": "c",
                    "scopes": [],
                    "expires_at": soon + "+00:00",
                },
            )

        verifier = self._verifier(handler)
        anyio.run(verifier.verify_token, "simba_at_short")
        ((expires, _),) = verifier._cache.values()
        assert expires - time.monotonic() <= 5.5


@pytest.mark.parametrize(
    "value, expected", [("1", True), ("true", True), ("YES", True), ("0", False), ("", False)]
)
def test_flag_parsing(monkeypatch, value, expected):
    monkeypatch.setenv("MCP_OAUTH_ENABLED", value)
    assert oauth.oauth_enabled() is expected
