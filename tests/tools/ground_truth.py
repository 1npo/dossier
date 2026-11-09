#!/usr/bin/env python3
"""Score a dossier's reports against a ground truth file (plan 010, D18).

    python3 tests/tools/ground_truth.py TRUTH REPORTS_DIR [--review FILE]

TRUTH is `{"entry_points": [{"kind", "key", "where"}], "io": [{"direction", "category", "key", "where"}]}`. A truth row matches when a
row of its home card contains its `key` (backticks ignored). Home cards: `entry.catalog` for entry points, `io.inputs` and `io.outputs`
for the two directions. Entry points get recall and precision (a dossier row is unmatched when no truth key is in it); inputs and
outputs get recall, and their unmatched rows are listed but not scored. Prints the figures. With --review, writes every
disagreement there for a person to rule on. This tool holds no data of its own and never changes either input.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HOME = {"entry": "entry.catalog", "input": "io.inputs", "output": "io.outputs"}
LABEL = {"entry": "entry points", "input": "inputs", "output": "outputs"}


def _norm(text) -> str:
    return str(text).replace("`", "")


_CITATION = re.compile(r"\[\[([^\]|]*?)(?:\|([^\]]*))?\]\]")


def _text(row: str) -> str:
    """The row with each `[[target|label]]` citation cut to its label, which the reader sees; targets are not claims (`201` must not match `...:171-201`)."""
    return _CITATION.sub(lambda m: m.group(2) or "", row)


def card_rows(reports: Path, card_id: str) -> list[str]:
    """One string per table row of the card, cells joined with ` | `. No such card gives []."""
    rows = []
    for f in sorted(Path(reports).glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for card in data.get("cards", []) if isinstance(data, dict) else []:
            if card.get("card") != card_id:
                continue
            for block in card.get("blocks", []):
                for row in block.get("rows", []) if block.get("type") == "table" else []:
                    rows.append(" | ".join(_norm(c) for c in row.get("cells", [])))
    return rows


def _side(truth_rows: list[dict], dossier_rows: list[str], precision: bool) -> dict:
    """One entry per truth row, so rows sharing a key keep their own `where`. `where` maps a key to all its lines, in order."""
    keys = [(t["key"], t.get("where", "")) for t in truth_rows]
    texts = [_text(r) for r in dossier_rows]
    hit = [any(_norm(k) in t for t in texts) for k, _ in keys]
    where: dict = {}
    for k, w in keys:
        where.setdefault(k, []).append(w)
    unmatched = [r for r, t in zip(dossier_rows, texts) if not any(_norm(k) in t for k, _ in keys)]
    out = {"matched": [k for (k, _), h in zip(keys, hit) if h], "missed": [k for (k, _), h in zip(keys, hit) if not h],
           "missed_where": [w for (_, w), h in zip(keys, hit) if not h], "unmatched": unmatched, "where": where,
           "recall": sum(hit) / len(keys) if keys else None}
    if precision:
        out["precision"] = (len(dossier_rows) - len(unmatched)) / len(dossier_rows) if dossier_rows else None
    return out


def score(truth_path, reports) -> dict:
    """`{"entry": side, "input": side, "output": side}`, each with matched, missed, unmatched, where, recall (and precision for entry)."""
    truth = json.loads(Path(truth_path).read_text(encoding="utf-8"))
    out = {"entry": _side(truth.get("entry_points", []), card_rows(reports, HOME["entry"]), True)}
    for d in ("input", "output"):
        out[d] = _side([t for t in truth.get("io", []) if t.get("direction") == d], card_rows(reports, HOME[d]), False)
    return out


def _pct(x) -> str:
    return "n/a" if x is None else f"{round(x * 100)}%"


def summary(result: dict) -> list[str]:
    lines = []
    for side in ("entry", "input", "output"):
        s = result[side]
        line = f"{LABEL[side]}: recall {_pct(s['recall'])}"
        if "precision" in s:
            line += f", precision {_pct(s['precision'])}"
        lines.append(f"{line} ({len(s['matched'])} matched, {len(s['missed'])} missed, {len(s['unmatched'])} unmatched)")
    return lines


def review(result: dict) -> str:
    out = ["# Ground truth disagreements", "", "Not ruled on. Phase 4a rules on each one.", ""]
    for side in ("entry", "input", "output"):
        s = result[side]
        out += [f"## {LABEL[side]}", "", f"### Missed by the dossier ({len(s['missed'])})", ""]
        out += [f"- `{k}` (truth: {w})" for k, w in zip(s["missed"], s["missed_where"])] or ["- none"]
        out += ["", f"### In the dossier but not in the truth ({len(s['unmatched'])})", ""]
        out += [f"- {r}" for r in s["unmatched"]] or ["- none"]
        out.append("")
    return "\n".join(out)


def main(argv=None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    path = None
    if "--review" in args:
        i = args.index("--review")
        if i + 1 >= len(args):
            print(__doc__)
            return 2
        path = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2:
        print(__doc__)
        return 2
    result = score(args[0], args[1])
    print("\n".join(summary(result)))
    if path:
        Path(path).write_text(review(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
