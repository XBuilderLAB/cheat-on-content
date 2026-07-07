#!/usr/bin/env python3
"""Generate a static Star History chart (docs/star-history.svg) in the
authentic star-history.com hand-drawn (xkcd) style.

Why static: GitHub now restricts stargazer `starred_at` timestamps to a
repo's own admins/collaborators, so star-history.com's anonymous <img>
embed no longer renders. This reads the data with your own authenticated
`gh` token (works because you're an admin) and writes a self-contained SVG
that matches star-history's look — embedded xkcd font, wobbly hand-drawn
axes/line, #dd4528 series color, legend + watermark.

Usage:
    gh auth status
    python3 tools/gen-star-history.py      # -> docs/star-history.svg

Jitter is seeded, so identical star data always yields an identical SVG
(no spurious diffs when the scheduled workflow re-runs).
"""
import datetime as dt
import math
import os
import random
import subprocess
import sys

REPO = "XBuilderLAB/cheat-on-content"
HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "..", "docs", "star-history.svg")
FONT_CSS = os.path.join(HERE, "xkcd-font.css")

LINE = "#dd4528"   # star-history single-series color
INK = "#000000"    # axes / labels
MUTE = "#666666"   # watermark

random.seed(20260707)   # deterministic wobble


def fetch_timestamps(repo):
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
    for s in (1000, 2000, 2500, 5000, 10000, 20000):
        if v / s <= 6:
            return math.ceil(v / s) * s, s
    return math.ceil(v / 50000) * 50000, 50000


def sketch(x1, y1, x2, y2, wob=1.6, seg=None):
    """Hand-drawn line: a path with jittered intermediate points."""
    dist = math.hypot(x2 - x1, y2 - y1)
    seg = seg or max(2, int(dist / 26))
    nx, ny = -(y2 - y1) / (dist or 1), (x2 - x1) / (dist or 1)  # normal
    pts = []
    for i in range(seg + 1):
        t = i / seg
        j = 0 if i in (0, seg) else random.uniform(-wob, wob)
        pts.append((x1 + (x2 - x1) * t + nx * j, y1 + (y2 - y1) * t + ny * j))
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return d


def build_svg(ts, repo):
    n = len(ts)
    t0, t1 = ts[0], ts[-1]
    span = (t1 - t0).total_seconds() or 1

    W, H = 800, 520
    L, R, T, B = 96, 34, 76, 78
    pw, ph = W - L - R, H - T - B
    ymax, ystep = nice_top(n)

    def X(t):
        return L + (t - t0).total_seconds() / span * pw

    def Y(v):
        return T + ph - (v / ymax) * ph

    # cumulative, sampled for a clean hand-drawn stroke
    step = max(1, n // 90)
    raw = [(ts[i], i + 1) for i in range(0, n, step)] + [(t1, n)]

    font = open(FONT_CSS).read().replace("&quot;", '"')
    XK = "font-family:'xkcd','Comic Sans MS',cursive"
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Star History - {repo}">',
         f'<defs><style>{font}</style></defs>',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']

    # title
    s.append(f'<text x="{W/2}" y="40" text-anchor="middle" style="{XK};font-size:26px" fill="{INK}">Star History</text>')

    # y gridlines + labels
    v = 0
    while v <= ymax + 1:
        y = Y(v)
        s.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L+pw}" y2="{y:.1f}" stroke="#e4e4e4" stroke-width="1"/>')
        lab = ("0" if v == 0 else (f"{v//1000}K" if v >= 1000 else str(v)))
        s.append(f'<text x="{L-14}" y="{y+6:.1f}" text-anchor="end" style="{XK};font-size:16px" fill="{INK}">{lab}</text>')
        v += ystep

    # x month ticks
    y0, m0 = t0.year, t0.month
    cur = dt.datetime(y0, m0, 1)
    if cur < t0:
        cur = dt.datetime(y0 + (m0 == 12), (m0 % 12) + 1, 1)
    months = []
    while cur <= t1:
        months.append(cur)
        cur = dt.datetime(cur.year + (cur.month == 12), (cur.month % 12) + 1, 1)
    for t in months:
        x = X(t)
        s.append(f'<text x="{x:.1f}" y="{T+ph+26:.1f}" text-anchor="middle" style="{XK};font-size:16px" fill="{INK}">{t.strftime("%b")}</text>')

    # hand-drawn axes
    s.append(f'<path d="{sketch(L, T+ph, L+pw, T+ph, 1.4)}" fill="none" stroke="{INK}" stroke-width="2" stroke-linecap="round"/>')
    s.append(f'<path d="{sketch(L, T+ph, L, T, 1.4)}" fill="none" stroke="{INK}" stroke-width="2" stroke-linecap="round"/>')

    # axis titles
    s.append(f'<text x="{L+pw/2:.1f}" y="{H-24}" text-anchor="middle" style="{XK};font-size:17px" fill="{INK}">Date</text>')
    s.append(f'<text x="26" y="{T+ph/2:.1f}" text-anchor="middle" transform="rotate(-90 26 {T+ph/2:.1f})" style="{XK};font-size:17px" fill="{INK}">GitHub Stars</text>')

    # the wobbly series line (chain of sketched segments)
    xy = [(X(t), Y(v)) for t, v in raw]
    d = "M{:.1f},{:.1f}".format(*xy[0])
    for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
        seg = sketch(x1, y1, x2, y2, 1.1)
        d += " L" + seg.split("M", 1)[1].replace(" L", " L")
    s.append(f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')
    # end marker
    ex, ey = xy[-1]
    s.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{LINE}"/>')

    # legend (color stroke sample + repo, upper-left inside plot)
    lx, ly = L + 24, T + 26
    s.append(f'<path d="{sketch(lx, ly, lx+34, ly, 1.0)}" fill="none" stroke="{LINE}" stroke-width="3" stroke-linecap="round"/>')
    s.append(f'<circle cx="{lx+17}" cy="{ly}" r="4" fill="{LINE}"/>')
    s.append(f'<text x="{lx+44}" y="{ly+6}" style="{XK};font-size:16px" fill="{INK}">{repo}</text>')

    # watermark
    s.append(f'<text x="{L+pw}" y="{T-16}" text-anchor="end" style="{XK};font-size:15px" fill="{MUTE}">star-history.com</text>')

    s.append('</svg>')
    return "\n".join(s)


def main():
    ts = fetch_timestamps(REPO)
    with open(OUT, "w") as f:
        f.write(build_svg(ts, REPO) + "\n")
    print(f"wrote {os.path.normpath(OUT)}  ({len(ts):,} stars, {ts[0].date()} → {ts[-1].date()})")


if __name__ == "__main__":
    main()
