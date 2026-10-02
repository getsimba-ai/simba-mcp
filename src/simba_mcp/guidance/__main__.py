"""Export standalone native Skills from packaged canonical guidance."""

import argparse
from pathlib import Path

from . import CONTENT, MANIFEST


def export(destination: Path, check: bool = False) -> bool:
    """Write or verify generated Skill files; never read client-controlled resource paths."""
    matches = True
    for topic in MANIFEST["topics"].values():
        for section, source in topic["sections"].items():
            relative = "SKILL.md" if section == "entrypoint" else f"references/{section}.md"
            target = destination / topic["skill"] / relative
            content = CONTENT.joinpath(source).read_text(encoding="utf-8")
            if check:
                matches &= target.is_file() and target.read_text(encoding="utf-8") == content
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8", newline="\n")
    return matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("skills"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not export(args.output_dir, args.check):
        parser.exit(1, "Native Skills differ from packaged guidance; regenerate them.\n")


if __name__ == "__main__":
    main()
