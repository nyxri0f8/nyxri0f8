"""Render neon telemetry cards (stats, languages, activity) from the GitHub GraphQL API.

Replaces flaky public services (github-readme-stats, activity-graph). Runs in the
snake workflow and writes SVGs into dist/, which is published to the `output` branch.
"""
import json
import os
import sys
import urllib.request
from datetime import date
from html import escape

USER = os.environ.get("GH_USER", "nyxri0f8")
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist"
# Markup languages swamp the byte counts (large static sites), so leave them out.
HIDDEN_LANGS = {"HTML", "CSS", "SCSS"}

QUERY = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

FONT = "'JetBrains Mono','Fira Code','SF Mono',Consolas,'Liberation Mono',monospace"
CYAN, MAGENTA, TEXT, DIM, BG = "#00f7ff", "#ff00e6", "#e6edf3", "#5c6f86", "#05070d"


def fetch():
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    if "errors" in data:
        raise SystemExit(data["errors"])
    return data["data"]["user"]


def chassis(w, h, title, inner):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<style>
  text {{ font-family: {FONT}; }}
  .dim {{ font-size: 11px; letter-spacing: 1.5px; fill: {DIM}; }}
  .in {{ opacity: 0; animation: in .6s ease-out forwards; }}
  @keyframes in {{ to {{ opacity: 1; }} }}
  .grow {{ transform-box: fill-box; transform-origin: left; transform: scaleX(0); animation: grow 1s ease-out forwards; }}
  @keyframes grow {{ to {{ transform: scaleX(1); }} }}
  .draw {{ stroke-dasharray: 3000; stroke-dashoffset: 3000; animation: draw 2.2s ease-out forwards; }}
  @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
</style>
<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="8" fill="{BG}" stroke="{CYAN}" stroke-opacity=".28"/>
<g stroke="{CYAN}" stroke-width="2.5" fill="none">
  <path d="M1 22V1h21"/><path d="M{w - 22} 1h21v21"/><path d="M{w - 1} {h - 22}v21h-21"/><path d="M22 {h - 1}H1v-21"/>
</g>
<text x="22" y="30" class="dim">▸ {escape(title)}</text>
<path d="M22 42H{w - 22}" stroke="{CYAN}" stroke-opacity=".18" stroke-dasharray="2 4"/>
{inner}
</svg>
"""


def stats_card(u):
    cc = u["contributionsCollection"]
    days = [d["contributionCount"] for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    langs = {e["node"]["name"] for r in u["repositories"]["nodes"] for e in r["languages"]["edges"]}
    metrics = [
        ("CONTRIBUTIONS / YR", cc["contributionCalendar"]["totalContributions"]),
        ("COMMITS", cc["totalCommitContributions"] + cc["restrictedContributionsCount"]),
        ("REPOSITORIES", u["repositories"]["totalCount"]),
        ("ACTIVE DAYS / YR", sum(1 for c in days if c)),
        ("LANGUAGES", len(langs)),
        ("PEAK DAY", max(days, default=0)),
    ]
    tiles = []
    for i, (label, value) in enumerate(metrics):
        x = 22 + (i % 2) * 206
        y = 58 + (i // 2) * 58
        color = CYAN if i % 3 != 1 else MAGENTA
        tiles.append(
            f'<g class="in" style="animation-delay:{0.15 * i:.2f}s">'
            f'<rect x="{x}" y="{y}" width="196" height="48" rx="4" fill="{color}" fill-opacity=".05" stroke="{color}" stroke-opacity=".3"/>'
            f'<rect x="{x}" y="{y + 10}" width="3" height="28" fill="{color}"/>'
            f'<text x="{x + 16}" y="{y + 19}" font-size="9.5" letter-spacing="1.5" fill="{DIM}">{label}</text>'
            f'<text x="{x + 16}" y="{y + 39}" font-size="18" font-weight="700" fill="{TEXT}">{value:,}</text>'
            f"</g>"
        )
    return chassis(450, 236, "TELEMETRY", "\n".join(tiles))


def langs_card(u):
    totals = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            if name in HIDDEN_LANGS:
                continue
            t =totals.setdefault(name, [0, e["node"]["color"] or CYAN])
            t[0] += e["size"]
    top = sorted(totals.items(), key=lambda kv: -kv[1][0])[:6]
    total = sum(v[0] for _, v in top) or 1
    rows = []
    for i, (name, (size, color)) in enumerate(top):
        pct = size / total * 100
        y = 64 + i * 27
        bar = max(4, 250 * pct / 100)
        rows.append(
            f'<g class="in" style="animation-delay:{0.12 * i:.2f}s">'
            f'<text x="22" y="{y + 9}" font-size="12" fill="{TEXT}">{escape(name)}</text>'
            f'<rect x="130" y="{y}" width="250" height="10" rx="2" fill="#0d1624"/>'
            f'<rect class="grow" style="animation-delay:{0.12 * i + 0.2:.2f}s" x="130" y="{y}" width="{bar:.1f}" height="10" rx="2" fill="{color}"/>'
            f'<text x="428" y="{y + 9}" font-size="11" fill="{DIM}" text-anchor="end">{pct:.1f}%</text>'
            f"</g>"
        )
    return chassis(450, 236, "LANGUAGE.MATRIX", "\n".join(rows))


def activity_card(u, days=60):
    cal = u["contributionsCollection"]["contributionCalendar"]["weeks"]
    series = [d for w in cal for d in w["contributionDays"]][-days:]
    counts = [d["contributionCount"] for d in series]
    w, h = 900, 250
    left, right, top, bottom = 50, 878, 62, 212
    peak = max(max(counts), 4)
    step = (right - left) / (len(counts) - 1)

    def pt(i, c):
        return left + i * step, bottom - (bottom - top) * c / peak

    pts = [pt(i, c) for i, c in enumerate(counts)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"{left},{bottom} {line} {right},{bottom}"

    grid = []
    for k in range(5):
        v = round(peak * k / 4)
        y = bottom - (bottom - top) * k / 4
        grid.append(f'<path d="M{left} {y:.1f}H{right}" stroke="{CYAN}" stroke-opacity=".07"/>')
        grid.append(f'<text x="{left - 10}" y="{y + 4:.1f}" font-size="10" fill="{DIM}" text-anchor="end">{v}</text>')
    for i in range(0, len(series), 10):
        x, _ = pts[i]
        label = date.fromisoformat(series[i]["date"]).strftime("%d %b").upper()
        grid.append(f'<text x="{x:.1f}" y="{bottom + 20}" font-size="10" fill="{DIM}" text-anchor="middle">{label}</text>')

    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{MAGENTA}"/>' for (x, y), c in zip(pts, counts) if c
    )
    total = sum(counts)
    inner = f"""
<defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="{CYAN}" stop-opacity=".35"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/>
</linearGradient></defs>
<text x="878" y="30" class="dim" text-anchor="end">{total} CONTRIBUTIONS · LAST {days} DAYS</text>
{''.join(grid)}
<polygon class="in" style="animation-delay:.6s" points="{area}" fill="url(#fill)"/>
<polyline class="draw" points="{line}" fill="none" stroke="{CYAN}" stroke-width="2" stroke-linejoin="round"/>
<g class="in" style="animation-delay:1.6s">{dots}</g>
"""
    return chassis(w, h, "ACTIVITY.WAVEFORM", inner)


def main():
    u = fetch()
    os.makedirs(OUT, exist_ok=True)
    for name, svg in [
        ("stats.svg", stats_card(u)),
        ("langs.svg", langs_card(u)),
        ("activity.svg", activity_card(u)),
    ]:
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(svg)
        print("wrote", name)


if __name__ == "__main__":
    main()
