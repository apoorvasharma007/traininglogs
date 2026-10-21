"""The version on the design page is the app's version: a release PR sets both."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_design_page_shows_the_version_in_pyproject() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    page = (ROOT / "docs" / "design.html").read_text()
    assert re.findall(r'<span class="app-version">([^<]+)</span>', page) == [version]
