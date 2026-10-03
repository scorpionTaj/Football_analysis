"""Generate docs/architecture.svg, the full data-pipeline diagram (explicit lane layout).

    python scripts/architecture_diagram.py docs/architecture.svg
    node scripts/svg_to_png.mjs docs/architecture.svg docs/architecture.png   # needs frontend Playwright
"""
import sys
from html import escape

W, H = 2600, 1560
INK, MUTED, LINE = "#1f2433", "#5a6072", "#8a90a3"
# lane: (title, accent, fill)
LANES = {
    "src": ("① Free data sources", "#4f86ea", "#eef3fd"),
    "ext": ("② Extract · Python sync_*", "#d06c3f", "#fdf1ea"),
    "wh": ("③ DuckDB warehouse · single writer", "#9b6ae0", "#f4effc"),
    "ml": ("④ Modelling · football-train-models", "#33a06f", "#ebf7f1"),
    "srv": ("⑤ Serving · football-publish", "#c2553a", "#fbeeea"),
    "app": ("⑥ Application", "#2f6fb0", "#eaf2fa"),
}
out, boxes = [], {}


def text(x, y, s, size=14, weight=400, color=INK, anchor="start"):
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" '
               f'text-anchor="{anchor}">{escape(s)}</text>')


def box(key, x, y, w, h, title, lines=(), accent=LINE, fill="#ffffff", store=False, dashed=False):
    boxes[key] = (x, y, w, h)
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    if store:  # cylinder for data stores
        out.append(f'<path d="M{x},{y+10} v{h-20} a{w/2},10 0 0 0 {w},0 v-{h-20}" fill="{fill}" stroke="{accent}" stroke-width="2"/>')
        out.append(f'<ellipse cx="{x+w/2}" cy="{y+10}" rx="{w/2}" ry="10" fill="{fill}" stroke="{accent}" stroke-width="2"/>')
        ty = y + 38
    else:
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{accent}" stroke-width="2"{dash}/>')
        ty = y + 24
    text(x + 14, ty, title, 15, 700)
    for i, line in enumerate(lines):
        text(x + 14, ty + 20 + i * 18, line, 13, 400, MUTED)


def side(key, where):
    x, y, w, h = boxes[key]
    return {"r": (x + w, y + h / 2), "l": (x, y + h / 2), "t": (x + w / 2, y), "b": (x + w / 2, y + h)}[where]


def arrow(a, b, sa="r", sb="l", label=None, dashed=False, color=LINE, lx=0, ly=-8):
    (x1, y1), (x2, y2) = side(a, sa), side(b, sb)
    if sa in "rl":
        mx = (x1 + x2) / 2
        d = f"M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}"
    else:
        my = (y1 + y2) / 2
        d = f"M{x1},{y1} C{x1},{my} {x2},{my} {x2},{y2}"
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"{dash} marker-end="url(#arrow)"/>')
    if label:
        text((x1 + x2) / 2 + lx, (y1 + y2) / 2 + ly, label, 12, 600, MUTED, "middle")


def route(points, dashed=False, color=LINE, label=None, at=None):
    d = "M" + " L".join(f"{x},{y}" for x, y in points)
    dash = ' stroke-dasharray="7 5"' if dashed else ""
    out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"{dash} stroke-linejoin="round" marker-end="url(#arrow)"/>')
    if label and at:
        out.append(f'<rect x="{at[0]-4}" y="{at[1]-14}" width="{len(label)*7+8}" height="20" rx="4" fill="#ffffff"/>')
        text(at[0], at[1], label, 12, 700, color)


def lane(key, x, y, w, h):
    title, accent, fill = LANES[key]
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" stroke="{accent}" stroke-opacity="0.35"/>')
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="40" rx="16" fill="{accent}"/>')
    out.append(f'<rect x="{x}" y="{y+24}" width="{w}" height="16" fill="{accent}"/>')
    text(x + 16, y + 27, title, 16, 700, "#ffffff")
    return accent


# ── header ────────────────────────────────────────────────────────────────────
text(40, 50, "Football Analysis — full data pipeline", 30, 800)
text(40, 80, "Free sources → extraction → tested DuckDB warehouse → walk-forward models → verified publishing → API → web app", 16, 400, MUTED)

# ── orchestration band ───────────────────────────────────────────────────────
out.append(f'<rect x="40" y="105" width="{W-80}" height="120" rx="16" fill="#f6f7fb" stroke="#c8ccd8"/>')
text(56, 132, "Orchestration & triggers", 16, 700)
box("dag", 56, 140, 560, 76, "Schedules: systemd timers (or Dagster / compose)",
    ["football-sync --quick every 6 h · full refresh daily 04:30", "flock: one DuckDB-writing run at a time · ntfy alert on failure"])
box("cli", 640, 140, 420, 76, "CLI",
    ["football-sync [--quick | --bootstrap] · football-publish", "football-build-warehouse · football-train-models"])
box("set", 1084, 140, 330, 76, "Settings page", ["4-step refresh button → same pipeline, live status"])
box("mlfui", 1438, 140, 330, 76, "Developer UIs", ["dagster dev (lineage, runs) · mlflow ui (experiments)"])
text(1800, 175, "Every trigger runs the same steps; step 4 = dbt build", 14, 400, MUTED)
text(1800, 195, "→ retrain → publish. Freshness gates skip unchanged sources.", 14, 400, MUTED)

TOP, BOT = 250, 1090
# ── lanes ─────────────────────────────────────────────────────────────────────
a_src = lane("src", 40, TOP, 340, BOT - TOP)
a_ext = lane("ext", 400, TOP, 350, BOT - TOP)
a_wh = lane("wh", 770, TOP, 600, BOT - TOP)
a_ml = lane("ml", 1390, TOP, 360, BOT - TOP)
a_srv = lane("srv", 1770, TOP, 380, BOT - TOP)
a_app = lane("app", 2170, TOP, 390, BOT - TOP)

# sources
src = [
    ("fd", "Football-Data.co.uk", ["season CSVs + fixtures.csv", "results · stats · odds · 2005+", "15 leagues incl. 2nd divisions"], 110),
    ("ofx", "OpenFootball football.json", ["7 full-season 2026/27 calendars", "CC0 · no key"], 92),
    ("oft", "OpenFootball tournaments", ["Champions League · World Cup", "Club World Cup · CC0"], 92),
    ("tmk", "Transfermarkt Open Dataset", ["players · games · events · lineups", "transfers · clubs · CC0 snapshot"], 92),
    ("tsd", "TheSportsDB v1 (capped)", ["next/last events · standings", "event details · club & league media"], 92),
]
y = TOP + 60
for key, t, ls, h in src:
    box(key, 56, y, 308, h, t, ls, a_src)
    y += h + 28

# extract
ext = [
    ("hist", "history.py", ["lands 2005+ CSVs untouched", "→ data/raw/yyYY/league.csv"], 92, "fd"),
    ("ing", "ingest.py", ["validated complete seasons", "partition swap · SHA-256 audit"], 92, None),
    ("rec", "recent.py · fixtures.py", ["open_fixtures.py · fixtures + early", "provisional scores before Football-Data"], 92, "ofx"),
    ("tour", "tournaments.py", ["UCL / World Cup / Club WC", "stages · scores · goal events"], 92, "oft"),
    ("opl", "open_players.py · transfers.py", ["profiles · season stats", "match context · timelines · lineups"], 92, "tmk"),
    ("med", "players · media · event_details", ["reference_standings.py", "capped enrichment + artwork"], 92, "tsd"),
]
y = TOP + 60
for key, t, ls, h, _ in ext:
    box(key, 416, y, 318, h, t, ls, a_ext)
    y += h + 18
box("gate", 416, y + 4, 318, 70, "sync_state · freshness gates", ["source_sync_cache: skip fresh / unchanged"], a_ext, "#fff7ef", dashed=True)

for key, *_, s in ext:
    if s:
        arrow(s, key)
arrow("fd", "ing")
arrow("fd", "rec")

# warehouse
box("land", 790, TOP + 60, 260, 92, "Landing zone", ["data/raw/yyYY/league.csv", "UTF-8 · immutable seasons"], a_wh, "#ffffff", store=True)
box("main", 790, TOP + 250, 260, 260, "main.* app tables", ["matches · recent_matches", "recent_events · fixtures", "tournament_matches/goals", "event_timeline · event_lineups", "players · open_players · transfers", "team_media · standings", "ingestion_runs · source_sync_cache", "prediction tables (from ④)"],
    a_wh, "#ffffff", store=True)
box("pst", 790, TOP + 600, 260, 110, "pipeline_status", ["dbt results · layer row counts", "source freshness per check", "→ /api/v1/pipeline"], a_wh, "#ffffff", store=True)
out.append(f'<rect x="1080" y="{TOP+56}" width="274" height="{BOT-TOP-80}" rx="12" fill="#ffffff" fill-opacity="0.6" stroke="{a_wh}" stroke-dasharray="6 4"/>')
text(1094, TOP + 80, "dbt build · warehouse/", 15, 700, a_wh)
box("stg", 1094, TOP + 96, 246, 74, "staging", ["stg_fd__results · stg_app__fixtures"], a_wh)
box("int", 1094, TOP + 200, 246, 60, "intermediate", ["int_team_matches"], a_wh)
box("mrt", 1094, TOP + 290, 246, 74, "marts", ["fct_match (113k) · mart_team_season"], a_wh)
box("ftr", 1094, TOP + 394, 246, 92, "ml.ml_match_features + elo", ["Elo · pi-ratings · EWMA form", "one Elo for app and model"], a_wh)
box("tst", 1094, TOP + 516, 246, 150, "31 nodes · data tests", ["unique / not-null keys", "double round-robin", "odds overround sanity", "one match per team per day", "Elo SQL = Python engine"], a_wh, "#fbf8ff", dashed=True)
text(1094, TOP + 700, "Failing test ⇒ build fails ⇒", 13, 600, MUTED)
text(1094, TOP + 718, "nothing is retrained or published", 13, 600, MUTED)

arrow("hist", "land")
for key in ("ing", "rec", "tour", "opl", "med"):
    arrow(key, "main", color="#b9a3df")
arrow("land", "stg")
arrow("main", "stg")
arrow("stg", "int", "b", "t")
arrow("int", "mrt", "b", "t")
arrow("mrt", "ftr", "b", "t")
arrow("tst", "pst", "l", "r", dashed=True)

# modelling
box("cand", 1406, TOP + 60, 328, 128, "8 candidate models", ["base-rate · Elo-only · logistic regression", "LightGBM · Poisson + Dixon-Coles", "ensemble (champion pool)", "market-blend · closing line (benchmarks)"], a_ml)
box("wf", 1406, TOP + 216, 328, 92, "Walk-forward evaluation", ["train ≤ S−2 · calibrate S−1 · test S", "RPS · log loss · Brier · ECE · accuracy"], a_ml)
box("sel", 1406, TOP + 336, 328, 92, "Champion selection", ["best RPS without odds (full run weekly)", "routine runs: champion refit ~15 s"], a_ml)
box("mlf", 1406, TOP + 456, 328, 92, "MLflow", ["params · per-season metrics", "calibration bins · git SHA"], a_ml, "#ffffff", store=True)
box("outp", 1406, TOP + 586, 328, 110, "Model outputs", ["model_runs · match_predictions", "forecast_history (journal on change)", "ml.backtest_predictions"], a_ml, "#ffffff", store=True)
text(1406, TOP + 730, "Champion today: ensemble", 14, 700, a_ml)
text(1406, TOP + 750, "log loss 0.967 · RPS 0.1946 · acc 53.4%", 13, 400, MUTED)
text(1406, TOP + 768, "closes 89% of the gap to the closing line", 13, 400, MUTED)

arrow("ftr", "cand")
arrow("cand", "wf", "b", "t")
arrow("wf", "sel", "b", "t")
arrow("sel", "mlf", "b", "t")
arrow("mlf", "outp", "b", "t")
route([(1406, TOP + 680), (1380, TOP + 680), (1380, TOP + 790), (1066, TOP + 790), (1066, TOP + 470), (1054, TOP + 470)], dashed=True, color=a_ml, label="predictions written back", at=(1110, TOP + 784))

# serving
box("dig", 1786, TOP + 60, 348, 92, "1 · Row digest per table", ["compared with snapshot_manifest", "unchanged tables are skipped"], a_srv)
box("cpy", 1786, TOP + 180, 348, 92, "2 · COPY changed → table__next", ["row counts verified server-side"], a_srv)
box("swp", 1786, TOP + 300, 348, 92, "3 · One-transaction swap", ["drop old · rename · rebuild views", "update manifest (readers never see a mix)"], a_srv)
box("pg", 1786, TOP + 430, 348, 110, "PostgreSQL · Supabase", ["private schema (no anon access)", "app tables + mart_team_season", "+ model_runs + pipeline_status"], a_srv, "#ffffff", store=True)
box("sq", 1786, TOP + 580, 348, 100, "SQLite fallback", ["data/football.sqlite3", "rebuilt from DuckDB, atomic rename"], a_srv, "#ffffff", store=True)
text(1786, TOP + 720, "Only changed tables are copied · 337 of 500 MB", 13, 400, MUTED)
text(1786, TOP + 738, "ntfy alert above 85% of the Supabase quota", 13, 400, MUTED)

route([(1050, TOP + 290), (1062, TOP + 290), (1062, TOP + 48), (1760, TOP + 48), (1760, TOP + 106), (1784, TOP + 106)], color=a_srv, label="served tables (app + marts + model runs)", at=(1100, TOP + 52))
arrow("dig", "cpy", "b", "t")
arrow("cpy", "swp", "b", "t")
arrow("swp", "pg", "b", "t")
arrow("swp", "sq", "l", "l", label="")

# app
box("api", 2186, TOP + 60, 358, 200, "FastAPI /api/v1", ["catalog · teams · matches · match-detail", "analysis · standings · shots · tournaments", "players · transfers · predictions", "models (leaderboard) · pipeline (health)", "quality · refresh", "gzip · ETag / Cache-Control"], a_app)
box("fail", 2186, TOP + 285, 358, 84, "Store selection", ["Postgres first, SQLite on outage", "DuckDB directly for local development"], a_app, "#f4f8fd", dashed=True)
box("web", 2186, TOP + 400, 358, 200, "Next.js + HeroUI frontend", ["Explore: Overview · Matches · Tables · Cups", "Analyze: Clubs · Players · Analysis · Shots", "Model: Predictions · Model Lab", "Data: Data Quality + Pipeline health", "Settings: themes · refresh", "axe-checked WCAG A/AA"], a_app)
box("user", 2186, TOP + 640, 358, 70, "Analyst / user", ["browser · mobile-responsive"], a_app)

arrow("pg", "api")
route([(2134, TOP + 630), (2160, TOP + 630), (2160, TOP + 327), (2184, TOP + 327)], dashed=True, color=a_srv, label="fallback", at=(2088, TOP + 650))
arrow("api", "fail", "b", "t")
arrow("fail", "web", "b", "t")
arrow("web", "user", "b", "t")

# ── quality / CI band ─────────────────────────────────────────────────────────
out.append(f'<rect x="40" y="{BOT+20}" width="{W-80}" height="250" rx="16" fill="#f6f7fb" stroke="#c8ccd8"/>')
text(56, BOT + 48, "Quality gates & CI (GitHub Actions on every push)", 16, 700)
qa = [
    ("pytest", ["adapters · API contracts · leakage", "models · provisional results", "publish + parity on temp PostgreSQL"]),
    ("dbt on fixture data", ["scripts/ci_warehouse.sh", "2 Premier League seasons", "all models + data tests"]),
    ("Dagster definitions", ["dagster definitions validate", "assets · jobs · schedules load"]),
    ("Frontend", ["eslint · tsc · next build", "Playwright e2e (17 flows)", "axe WCAG A/AA scans"]),
    ("Runtime observability", ["pipeline_status → Pipeline health", "source freshness · test results", "Model Lab leaderboard"]),
]
x = 56
for t, ls in qa:
    box("qa_" + t, x, BOT + 64, 480, 110, t, ls, "#7a8094")
    x += 500
text(56, BOT + 214, "Leakage guard: every feature uses only matches before the kickoff date; same-day results update state only after the whole day.", 14, 400, MUTED)
text(56, BOT + 238, "Secrets stay in .env (gitignored); Supabase schema is private. Raw data, DuckDB, SQLite, mlruns/ and .dagster/ are never committed.", 14, 400, MUTED)

H = BOT + 290
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif">
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{LINE}"/></marker></defs>
<rect width="{W}" height="{H}" fill="#ffffff"/>
{chr(10).join(out)}
</svg>'''
open(sys.argv[1], "w").write(svg)
print(W, H)
