#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.27.0"

frontend = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
backend = (ROOT / "backend/pyproject.toml").read_text(encoding="utf-8")
main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
installer = (ROOT / "packaging/debian/install-from-github.sh").read_text(encoding="utf-8")
readme = (ROOT / "README.md").read_text(encoding="utf-8")

assert frontend["version"] == VERSION
assert lock["version"] == VERSION
assert lock["packages"][""]["version"] == VERSION
assert re.search(rf'^version = "{re.escape(VERSION)}"$', backend, re.MULTILINE)
assert f'version="{VERSION}"' in main
assert f"GIT_REF=${{TRANSMY_GIT_REF:-v{VERSION}}}" in installer
assert f"PACKAGE_VERSION=${{TRANSMY_VERSION:-{VERSION}}}" in installer
assert f"/v{VERSION}/packaging/debian/install-from-github.sh" in readme
assert not re.search(r"\bLot\s+\d+\b", ROOT.joinpath("frontend/src/App.vue").read_text(encoding="utf-8"))

print(f"Release metadata is aligned on {VERSION}.")
