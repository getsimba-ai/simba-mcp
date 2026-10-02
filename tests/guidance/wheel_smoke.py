"""Run with python -I against one built wheel, independently of the source tree."""

import sys
import tempfile
from pathlib import Path


def main():
    wheel = next(Path(sys.argv[1]).glob("simba_mcp-*.whl")).resolve()
    sys.path.insert(0, str(wheel))
    from simba_mcp import guidance
    from simba_mcp.guidance.__main__ import export

    assert ".whl" in guidance.__file__, guidance.__file__
    index = guidance.read_guidance()
    assert len(index["topics"]) == 6
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        export(target)
        assert export(target, check=True)
        for topic in index["topics"]:
            for section in topic["sections"]:
                assert "content" in guidance.read_guidance(topic["topic"], section)
    from importlib.resources import files

    html = files("simba_mcp").joinpath("ui/charts.html").read_text(encoding="utf-8")
    assert "ui/initialize" in html
    assert len(html.encode("utf-8")) <= 30_000
    print("Wheel guidance resources and standalone native export verified.")


if __name__ == "__main__":
    main()
