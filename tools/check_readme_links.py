"""Check that local README links point at files in the repository."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def main():
    missing = []
    text = README.read_text(encoding="utf-8")
    for match in LINK_RE.finditer(text):
        target = match.group(1).split("#", 1)[0]
        if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target):
            continue
        if not (ROOT / target).exists():
            missing.append(target)

    if missing:
        print("Missing README link targets:")
        for target in missing:
            print(f"  {target}")
        return 1
    print("README links OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
