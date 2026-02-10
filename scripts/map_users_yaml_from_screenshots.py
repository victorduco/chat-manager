#!/usr/bin/env python3
"""
Map Telegram-export-derived users YAML (username like 'user118497177') to real handles
using OCR results from screenshots/users.json.

Heuristic:
  - Match by normalized full name (first_name + last_name) if available.
  - If only first_name exists, match by first_name only if it maps uniquely.

Outputs:
  - A copied YAML with username replaced by handle (without '@') when matched.
  - A JSON report with matched/ambiguous/missing entries.

Example:
  python scripts/map_users_yaml_from_screenshots.py \
    --in-yaml out_intro_vastrik_design_20260210_115626/users.yaml \
    --users-json test_data/screenshots/users.json \
    --out-yaml out_intro_vastrik_design_20260210_115626/users.mapped.yaml
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _norm_name(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("\u200e", " ").replace("\u200f", " ")
    # Keep latin/cyrillic letters and digits as tokens.
    s = re.sub(r"[^0-9a-zа-яё]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _parse_simple_users_yaml(text: str) -> List[Dict[str, Any]]:
    """
    Parse YAML produced by scripts/telegram_intro_extract.py:
      - username: ...
        telegram_id: ...
        first_name: ...
        last_name: ...
        intro: true/false
    into a list of dicts.
    """
    users: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if not line.strip():
            continue
        if line.startswith("- "):
            if cur:
                users.append(cur)
            cur = {}
            line = line[2:]
        if cur is None:
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip()
        v = v.strip()
        if v.startswith('"') or v.startswith("'"):
            # JSON-style quoting was used by writer; use json.loads for double quotes.
            if v.startswith('"'):
                try:
                    v2 = json.loads(v)
                    v = v2
                except Exception:
                    v = v.strip('"')
            else:
                v = v.strip("'")
        if isinstance(v, str):
            if v in ("true", "false"):
                cur[k] = (v == "true")
                continue
            if v == "null":
                cur[k] = None
                continue
            # int?
            if re.fullmatch(r"-?\d+", v):
                try:
                    cur[k] = int(v)
                    continue
                except Exception:
                    pass
        cur[k] = v

    if cur:
        users.append(cur)
    return users


def _write_simple_users_yaml(path: Path, users: List[Dict[str, Any]]) -> None:
    def scalar(x: Any) -> str:
        if x is None:
            return "null"
        if isinstance(x, bool):
            return "true" if x else "false"
        if isinstance(x, int):
            return str(x)
        s = str(x)
        # quote if needed
        if s == "" or any(c in s for c in [":", "#", "\n", "\r", "\t", '"', "'"]) or s.strip() != s:
            return json.dumps(s, ensure_ascii=False)
        return s

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for u in users:
            f.write("- username: " + scalar(u.get("username", "")) + "\n")
            if u.get("telegram_id") is not None:
                f.write("  telegram_id: " + scalar(u.get("telegram_id")) + "\n")
            f.write("  first_name: " + scalar(u.get("first_name") or u.get("username") or "") + "\n")
            if u.get("last_name") is not None:
                f.write("  last_name: " + scalar(u.get("last_name")) + "\n")
            f.write("  intro: " + scalar(bool(u.get("intro"))) + "\n\n")


@dataclass
class Candidate:
    username: str  # no '@'
    handle: str
    name: str
    occurrences: int


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-yaml", required=True)
    ap.add_argument("--users-json", required=True)
    ap.add_argument("--out-yaml", required=True)
    ap.add_argument("--out-report", default=None)
    args = ap.parse_args()

    in_yaml = Path(args.in_yaml)
    users_json = Path(args.users_json)
    out_yaml = Path(args.out_yaml)
    out_report = Path(args.out_report) if args.out_report else out_yaml.with_suffix(".report.json")

    raw_yaml = in_yaml.read_text(encoding="utf-8", errors="replace")
    src_users = _parse_simple_users_yaml(raw_yaml)

    data = json.loads(users_json.read_text(encoding="utf-8"))
    ocr: List[Candidate] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        username = str(row.get("username") or "").strip().lstrip("@")
        handle = str(row.get("handle") or ("@" + username)).strip()
        name = str(row.get("name") or "").strip()
        occ = int(row.get("occurrences") or 0)
        if not username or not name:
            continue
        ocr.append(Candidate(username=username, handle=handle, name=name, occurrences=occ))

    by_full: Dict[str, List[Candidate]] = {}
    by_first: Dict[str, List[Candidate]] = {}
    for c in ocr:
        n = _norm_name(c.name)
        if not n:
            continue
        by_full.setdefault(n, []).append(c)
        first = n.split(" ", 1)[0]
        if first:
            by_first.setdefault(first, []).append(c)

    def choose(cands: List[Candidate]) -> Candidate:
        # Prefer most frequent in screenshots, then shortest handle (less garbage), then username.
        return sorted(cands, key=lambda x: (-x.occurrences, len(x.username), x.username))[0]

    mapped = 0
    ambiguous = 0
    missing = 0
    report = {"matched": [], "ambiguous": [], "missing": []}

    out_users: List[Dict[str, Any]] = []
    for u in src_users:
        username_before = str(u.get("username") or "")
        fn = str(u.get("first_name") or "").strip()
        ln = u.get("last_name")
        ln_s = str(ln).strip() if isinstance(ln, str) else ""
        full = _norm_name((fn + " " + ln_s).strip()) if ln_s else _norm_name(fn)

        picked: Optional[Candidate] = None
        reason = None

        if full and full in by_full:
            cands = by_full[full]
            if len(cands) == 1:
                picked = cands[0]
                reason = "full_name_exact"
            else:
                picked = choose(cands)
                reason = "full_name_multi_choose"
                ambiguous += 1
                report["ambiguous"].append(
                    {
                        "first_name": fn,
                        "last_name": ln_s or None,
                        "yaml_username": username_before,
                        "candidates": [{"handle": c.handle, "name": c.name, "occurrences": c.occurrences} for c in cands],
                        "picked": picked.handle,
                        "reason": reason,
                    }
                )
        elif fn:
            first = _norm_name(fn).split(" ", 1)[0]
            cands = by_first.get(first) or []
            # Only allow first-name-only match when unique.
            if len(cands) == 1:
                picked = cands[0]
                reason = "first_name_unique"

        if picked is None:
            missing += 1
            report["missing"].append(
                {
                    "first_name": fn or None,
                    "last_name": ln_s or None,
                    "yaml_username": username_before,
                }
            )
            out_users.append(dict(u))
            continue

        # Apply mapping: set YAML username to OCR username (no '@').
        new_u = dict(u)
        new_u["username"] = picked.username
        out_users.append(new_u)
        mapped += 1
        report["matched"].append(
            {
                "first_name": fn or None,
                "last_name": ln_s or None,
                "yaml_username": username_before,
                "mapped_to": picked.handle,
                "reason": reason,
            }
        )

    _write_simple_users_yaml(out_yaml, out_users)
    out_report.write_text(json.dumps(
        {
            "in_yaml": str(in_yaml),
            "users_json": str(users_json),
            "out_yaml": str(out_yaml),
            "stats": {"total": len(src_users), "mapped": mapped, "ambiguous": ambiguous, "missing": missing},
            **report,
        },
        ensure_ascii=False,
        indent=2,
    ), encoding="utf-8")

    print(f"Wrote {out_yaml} (mapped={mapped}/{len(src_users)}, missing={missing}, ambiguous={ambiguous})")
    print(f"Wrote {out_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

