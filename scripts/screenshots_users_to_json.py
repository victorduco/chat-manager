#!/usr/bin/env python3
"""
OCR Telegram-like screenshots to extract (name, @username) pairs and export to JSON.

Input: directory with screenshots (png/jpg/webp).
Output: JSON list with unique usernames, best-effort names, and source files.

Requires:
  - tesseract installed (brew install tesseract tesseract-lang)

Example:
  python scripts/screenshots_users_to_json.py \
    --input-dir test_data/screenshots \
    --out test_data/screenshots/users.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


HANDLE_RE = re.compile(r"@([A-Za-z0-9_]{3,32})")


def _run_tesseract(path: Path, *, lang: str, psm: int) -> str:
    # stdout output; suppress tesseract stderr noise.
    cmd = [
        "tesseract",
        str(path),
        "stdout",
        "-l",
        lang,
        "--psm",
        str(psm),
        "-c",
        "preserve_interword_spaces=1",
    ]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    try:
        return r.stdout.decode("utf-8", errors="replace")
    except Exception:
        return r.stdout.decode(errors="replace")


def _clean_name(s: str) -> str:
    # Remove handles and most UI garbage, keep letters/numbers/spaces/dots/hyphens.
    s = HANDLE_RE.sub("", s)
    s = s.replace("\u200e", " ").replace("\u200f", " ")
    s = re.sub(r"[|›»«©®™•·●◆■□▶▷▸▹➤➜→←↑↓]+", " ", s)
    s = re.sub(r"[^0-9A-Za-zА-Яа-яЁё .,'’`\\-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -.,'")
    # Drop very short / obviously non-name strings.
    if len(s) < 2:
        return ""
    return s


def _name_score(name: str) -> Tuple[int, int, int]:
    # Higher is better. Prefer longer alphabetic content, fewer weird bits.
    letters = sum(1 for c in name if c.isalpha())
    spaces = name.count(" ")
    length = len(name)
    return (letters, spaces, length)


@dataclass
class UserHit:
    username: str  # stored lowercase without '@'
    handle: str  # original best handle formatting "@foo"
    name: str = ""
    sources: List[str] = field(default_factory=list)
    occurrences: int = 0

    def consider_name(self, candidate: str) -> None:
        cand = _clean_name(candidate)
        if not cand:
            return
        if not self.name:
            self.name = cand
            return
        if _name_score(cand) > _name_score(self.name):
            self.name = cand


def _iter_images(input_dir: Path) -> Iterable[Path]:
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    for p in sorted(input_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            yield p


def _extract_pairs(ocr_text: str) -> List[Tuple[str, str]]:
    """
    Returns list of (handle, name_candidate) from OCR text.
    Name may be empty if not found.
    """
    lines = [ln.strip() for ln in (ocr_text or "").splitlines()]
    out: List[Tuple[str, str]] = []

    last_name_line = ""
    for ln in lines:
        if not ln:
            continue

        handles = HANDLE_RE.findall(ln)
        if handles:
            # Heuristic: if this line has non-handle content, use it. Otherwise use previous name line.
            name_candidate = _clean_name(ln)
            if not name_candidate:
                name_candidate = last_name_line

            for h in handles:
                out.append((f"@{h}", name_candidate))
            continue

        # Update last name line if it contains letters.
        cleaned = _clean_name(ln)
        if cleaned and any(c.isalpha() for c in cleaned):
            last_name_line = cleaned

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lang", default="eng+rus")
    ap.add_argument("--psm", type=int, default=6)
    ap.add_argument("--save-ocr-text", action="store_true", help="Also save per-image OCR txt next to output JSON")
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    users: Dict[str, UserHit] = {}

    for img in _iter_images(input_dir):
        ocr = _run_tesseract(img, lang=args.lang, psm=args.psm)
        if args.save_ocr_text:
            txt_path = out_path.parent / (img.name + ".ocr.txt")
            txt_path.write_text(ocr, encoding="utf-8", errors="replace")

        pairs = _extract_pairs(ocr)
        for handle, name in pairs:
            key = handle.lstrip("@").lower()
            hit = users.get(key)
            if hit is None:
                hit = UserHit(username=key, handle=f"@{key}")
                users[key] = hit
            hit.occurrences += 1
            if str(img) not in hit.sources:
                hit.sources.append(str(img))
            hit.consider_name(name)

    result = []
    for key in sorted(users.keys()):
        u = users[key]
        result.append(
            {
                "username": u.username,  # without '@', lowercase
                "handle": u.handle,  # with '@'
                "name": u.name or None,
                "occurrences": u.occurrences,
                "sources": u.sources,
            }
        )

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} (users={len(result)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

