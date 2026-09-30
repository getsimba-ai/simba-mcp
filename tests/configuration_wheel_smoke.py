"""Verify non-editable wheel diagnostics, isolated from checkout imports."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    wheel = next(Path(sys.argv[1]).glob("simba_mcp-*.whl")).resolve()
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "installed"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(target),
                str(wheel),
            ],
            check=True,
        )
        code = "import sys,runpy;sys.path.insert(0,sys.argv.pop(1));runpy.run_module('simba_mcp.configuration',run_name='__main__')"
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SIMBA_", "MCP_"))}
        for args, setting, expected in [
            (["--check"], {}, 0),
            ([], {}, 0),
            ([], {"SIMBA_TOOL_DESCRIPTIONS": "synthetic-secret-invalid"}, 2),
            ([], {"SIMBA_TOOL_PROFILE": "synthetic-secret-invalid"}, 2),
            ([], {"SIMBA_API_REQUEST_POLICY_JSON": "synthetic-secret-invalid"}, 2),
        ]:
            result = subprocess.run(
                [sys.executable, "-I", "-c", code, str(target), *args],
                cwd=directory,
                env={**env, **setting},
                check=False,
                capture_output=True,
                text=True,
            )
            assert result.returncode == expected, result.stdout + result.stderr
            assert "synthetic-secret-invalid" not in result.stdout + result.stderr
            assert "Traceback" not in result.stderr
            if not args:
                assert isinstance(json.loads(result.stdout), dict)
    print("Installed wheel configuration checks and secret-free invalid settings verified")


if __name__ == "__main__":
    main()
