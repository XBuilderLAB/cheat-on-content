#!/usr/bin/env python3
"""
diff_pct.py — char-level diff_pct on normalized text.

Replaces the legacy line-level diff in cheat-shoot Phase 3b, which
inflated diff_pct for spoken-style transcripts (long markdown lines vs
short transcribed lines) and falsely triggered v2 re-predictions.

Algorithm:
  1. Normalize both files (strip markdown elements, collapse whitespace)
  2. Char-level Levenshtein distance / max(len_a, len_b)
  3. Output integer 0-100

Backend selection:
  - Prefer rapidfuzz (C-backed, ~ms for 10KB strings) — `pip install rapidfuzz`
  - Fallback to stdlib difflib.SequenceMatcher (slower but always available)

Usage:
  python3 tools/diff_pct.py <orig_path> <new_path>
Output:
  Single integer 0-100 on stdout.

Exit codes:
  0 = success (number on stdout)
  2 = bad args
  3 = file read error
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


# Markdown / formatting noise that whisper-style transcripts don't have.
# Stripping these from BOTH sides equalizes the surface so we measure
# content-similarity, not formatting-similarity.
_MARKDOWN_HEADER = re.compile(r"^#+\s+.*$", re.MULTILINE)
_MARKDOWN_HR = re.compile(r"^[-=*]{3,}\s*$", re.MULTILINE)
_MARKDOWN_BLOCKQUOTE = re.compile(r"^>+\s*", re.MULTILINE)
_MARKDOWN_LIST = re.compile(r"^[-*+]\s+|^\d+\.\s+", re.MULTILINE)
_FORMATTING_PUNCT = re.compile(r"[「」『』\"`*_~]")
_ALL_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Strip markdown / formatting noise, collapse to single 'sentence'."""
    text = _MARKDOWN_HEADER.sub("", text)
    text = _MARKDOWN_HR.sub("", text)
    text = _MARKDOWN_BLOCKQUOTE.sub("", text)
    text = _MARKDOWN_LIST.sub("", text)
    text = _FORMATTING_PUNCT.sub("", text)
    text = _ALL_WHITESPACE.sub("", text)
    return text


def diff_pct(a: str, b: str) -> tuple[int, str]:
    """Return (0-100 int, backend_name)."""
    a_n = normalize(a)
    b_n = normalize(b)
    max_len = max(len(a_n), len(b_n))
    if max_len == 0:
        return 0, "trivial"

    # Try rapidfuzz first (faster + matches the spec)
    try:
        from rapidfuzz.distance import Levenshtein

        d = Levenshtein.distance(a_n, b_n)
        return (d * 100) // max_len, "rapidfuzz"
    except ImportError:
        pass

    # Fallback to stdlib difflib SequenceMatcher.
    # ratio() returns 0-1 similarity; we want 0-100 distance.
    # SequenceMatcher's algorithm differs from pure Levenshtein but
    # for our use case (semantic content similarity) it's well-correlated.
    from difflib import SequenceMatcher

    sm = SequenceMatcher(a=a_n, b=b_n, autojunk=False)
    sim = sm.ratio()
    return int(round((1 - sim) * 100)), "difflib"


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: diff_pct.py <orig_path> <new_path>", file=sys.stderr)
        return 2

    try:
        a = Path(sys.argv[1]).read_text(encoding="utf-8")
        b = Path(sys.argv[2]).read_text(encoding="utf-8")
    except OSError as e:
        print(f"read error: {e}", file=sys.stderr)
        return 3

    pct, backend = diff_pct(a, b)
    print(pct)
    # backend goes to stderr so callers can inspect without parsing stdout
    print(f"backend={backend} a_norm_len={len(normalize(a))} b_norm_len={len(normalize(b))}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
