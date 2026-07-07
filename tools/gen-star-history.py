#!/usr/bin/env python3
"""Generate a static Star History chart (docs/star-history.svg).

Why static: GitHub now restricts the stargazer `starred_at` timestamps to a
repo's own admins/collaborators, so star-history.com's anonymous <img> embed
no longer renders in the README. This script reads the data with your own
authenticated `gh` token (works because you're an admin/collaborator) and
writes a self-contained SVG that never depends on star-history uptime.

Usage:
    gh auth status                 # make sure you're logged in as an admin
    python3 tools/gen-star-history.py
    # -> writes docs/star-history.svg

Refresh whenever you want an updated snapshot; commit the regenerated SVG.
"""
import datetime as dt
import json
import math
import os
import subprocess
import sys

REPO = "XBuilderLAB/cheat-on-content"
OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "star-history.svg")


def fetch_timestamps(repo):
    """Return sorted list of datetime for every star, via authenticated gh."""
    out = subprocess.run(
        ["gh", "api", "--paginate",
         "-H", "Accept: application/vnd.github.star+json",
         f"/repos/{repo}/stargazers?per_page=100",
         "-q", ".[].starred_at"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        sys.exit(f"gh api failed:\n{out.stderr}")
    ts = [dt.datetime.strptime(l.strip(), "%Y-%m-%dT%H:%M:%SZ")
          for l in out.stdout.splitlines() if l.strip()]
    ts.sort()
    return ts


def nice_top(v):
    for s in (500, 1000, 2000, 2500, 5000):
        if v / s <= 6:
            return math.ceil(v / s) * s, s
    return math.ceil(v / 10000) * 10000, 10000


def build_svg(ts, repo):
    n = len(ts)
    t0, t1 = ts[0], ts[-1]
    span = (t1 - t0).total_seconds() or 1

    pts = []
    step = max(1, n // 600)
    for i in range(0, n, step):
        pts.append((ts[i], i + 1))
    pts.append((t1, n))

    W, H = 820, 430
    L, R, T, B = 78, 58, 58, 52
    pw, ph = W - L - R, H - T - B
    ymax, ystep = nice_top(n)

    def X(t):
        return L + (t - t0).total_seconds() / span * pw

    def Y(v):
        return T + ph - (v / ymax) * ph

    NT = 6
    xticks = [t0 + dt.timedelta(seconds=span * k / (NT - 1)) for k in range(NT)]

    GREEN, GRID, AXIS, TXT, TITLE = "#3aa757", "#e8e8e8", "#9aa0a6", "#586069", "#24292f"
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Star History - {repo}">',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         f'<text x="{L}" y="34" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif" font-size="17" font-weight="700" fill="{TITLE}">★ Star History</text>',
         f'<text x="{W-R}" y="34" text-anchor="end" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif" font-size="12" fill="{AXIS}">{repo}</text>']
    v = 0
    while v <= ymax + 1:
        y = Y(v)
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        lab = f'{v//1000}k' if v >= 1000 else str(v)
        s.append(f'<text x="{L-10}" y="{y+4:.1f}" text-anchor="end" font-family="Arial,sans-serif" font-size="11" fill="{TXT}">{lab}</text>')
        v += ystep
    for t in xticks:
        x = X(t)
        s.append(f'<line x1="{x:.1f}" y1="{T+ph}" x2="{x:.1f}" y2="{T+ph+5}" stroke="{AXIS}" stroke-width="1"/>')
        s.append(f'<text x="{x:.1f}" y="{T+ph+20}" text-anchor="middle" font-family="Arial,sans-serif" font-size="11" fill="{TXT}">{t.strftime("%b %-d")}</text>')
    s.append(f'<line x1="{L}" y1="{T+ph}" x2="{L+pw}" y2="{T+ph}" stroke="{AXIS}" stroke-width="1.5"/>')
    poly = " ".join(f'{X(t):.1f},{Y(v):.1f}' for t, v in pts)
    s.append(f'<polygon points="{L},{T+ph} {poly} {L+pw},{T+ph}" fill="{GREEN}" fill-opacity="0.08"/>')
    s.append(f'<polyline points="{poly}" fill="none" stroke="{GREEN}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>')
    ex, ey = X(t1), Y(n)
    s.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" fill="{GREEN}"/>')
    s.append(f'<text x="{ex-8:.1f}" y="{ey-9:.1f}" text-anchor="end" font-family="Arial,sans-serif" font-size="12" font-weight="700" fill="{GREEN}">{n:,}★</text>')
    s.append(f'<text x="{L+pw}" y="{H-8}" text-anchor="end" font-family="Arial,sans-serif" font-size="10" fill="{AXIS}">snapshot {t1.strftime("%Y-%m-%d")} · star-history style</text>')
    s.append('</svg>')
    return "\n".join(s)


def main():
    ts = fetch_timestamps(REPO)
    svg = build_svg(ts, REPO)
    with open(OUT, "w") as f:
        f.write(svg + "\n")
    print(f"wrote {os.path.normpath(OUT)}  ({len(ts):,} stars, {ts[0].date()} → {ts[-1].date()})")


if __name__ == "__main__":
    main()
