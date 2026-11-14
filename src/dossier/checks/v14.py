"""V14: every function, class and variable in a component's Public surface carries a citation (an error).

Without one the reader cannot open the definition in the side panel. A name is written as `[[path:start-end|name]]`: the label is
the name, the range is the whole definition. Anything still in backticks after the `[[...]]` marks are taken out is a name with no
citation. The existing warning "mentions `x` without citing it" covers file paths only; this rule covers identifiers.
"""
from __future__ import annotations

import re

from dossier.render import markup

__all__ = ["CARD", "FIELD", "v14"]

CARD, FIELD = "components.detail", "public_surface"
TICKED = re.compile(r"`([^`\n]+)`")


def uncited(text: str) -> list[str]:
    """The backticked names in `text` that are not inside a [[...]] citation."""
    return [m.group(1) for m in TICKED.finditer(markup.INLINE_CITE.sub("", str(text or "")))]


def v14(reports: dict) -> list[str]:
    errors = []
    for entry in ((reports.get("components") or {}).get("cards") or []):
        if not isinstance(entry, dict) or entry.get("card") != CARD:
            continue
        for e in entry.get("entries") or []:
            if not isinstance(e, dict) or not isinstance(e.get("fields"), dict):
                continue
            names = uncited(e["fields"].get(FIELD))
            if names:
                shown = ", ".join(f"`{n}`" for n in names[:6]) + (", ..." if len(names) > 6 else "")
                errors.append(f"V14: Component details: the Public surface of {e.get('component')} names {shown} without a citation. "
                              "Write each as [[path:start-end|name]], with the range of its whole definition.")
    return errors
