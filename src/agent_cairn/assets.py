"""Load agent-facing text from ``assets/`` and fill ``{{name}}`` placeholders (design D10)."""

from __future__ import annotations

import re
from pathlib import Path

ASSETS_DIR = Path(__file__).parent / "assets"
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")


def fill(name: str, **values: str) -> str:
    """Return asset ``name`` with each ``{{key}}`` replaced by ``values[key]``.

    Raises:
        KeyError: the asset uses a placeholder that was not supplied.
    """
    text = (ASSETS_DIR / name).read_text(encoding="utf-8")
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], text)
