"""Protect dependency boundaries and the installed command after module moves."""

import ast
import subprocess
import sys
from pathlib import Path

from simba_mcp.evaluation import contracts, reporting
from simba_mcp.measurements import distribution


def imports(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield "." * node.level + (node.module or "")


def test_contracts_and_rendering_have_no_execution_dependencies():
    assert set(imports(contracts.__file__)) <= {"typing", "pydantic"}
    assert not set(imports(reporting.__file__))
    package = Path(contracts.__file__).parent
    for module in (package / "runner.py", package.parent / "benchmark.py"):
        assert not any("benchmark" in name or "performance" in name for name in imports(module))
    assert set(imports(package / "hosts" / "result_grading.py")) <= {"json", "re"}
    assert not any(
        "hosts" in name or "runner" in name for name in imports(package / "experiments.py")
    )


def test_cli_still_exposes_the_same_command():
    result = subprocess.run(
        [sys.executable, "-m", "simba_mcp.evaluation", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--samples" in result.stdout
    assert "--output-dir" in result.stdout


def test_shared_distribution_preserves_percentile_definition():
    assert distribution([4, 1, 3, 2]) == {
        "samples": 4,
        "min": 1,
        "median": 2.5,
        "p95": 4,
        "max": 4,
    }
