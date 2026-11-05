"""V5 checks for reports 13 and 14 that look at who and what a card names, not at its layout."""
from __future__ import annotations

RISK_SOURCES = ("extractor", "read")


def risk_source(reports: dict) -> list:
    """Every row of Risks says whether a tool found the risk (extractor) or Claude read it (read)."""
    entry = next((e for e in ((reports or {}).get("risks") or {}).get("cards") or [] if isinstance(e, dict) and e.get("card") == "risks.tracker"), None)
    if not entry or "blocks" not in entry:
        return []
    out = []
    for block in entry["blocks"]:
        columns = block.get("columns") or [] if isinstance(block, dict) else []
        if "Source" not in columns:
            continue
        at = columns.index("Source")
        for row in block.get("rows") or []:
            cells = row.get("cells") or []
            cell = str(cells[at]).strip() if at < len(cells) else ""
            if cell.lower() not in RISK_SOURCES:
                out.append(f"V5: Risks: Source must be extractor or read, found '{cell}'.")
    return out
