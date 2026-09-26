"""docs/tools.md is generated from the running server and must match it (#28)."""

from simba_mcp import reference
from simba_mcp.server import TOOLS


def test_committed_tool_reference_is_current():
    committed = reference.DOCS.read_text(encoding="utf-8")
    assert committed == reference.current(), (
        "docs/tools.md is out of date — run `python -m simba_mcp.reference` in this PR"
    )


def test_the_reference_states_the_real_tool_count_and_every_tool():
    page = reference.current()
    assert f"**{len(TOOLS)} tools**" in page
    for fn in TOOLS:
        assert f"### `{fn.__name__}`" in page


def test_types_render_readably():
    assert reference._type({"type": "string"}) == "string"
    assert reference._type({"type": "array", "items": {"type": "string"}}) == "list of string"
    optional = {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]}
    assert reference._type(optional) == "list of string (optional)"
