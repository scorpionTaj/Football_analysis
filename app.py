import html

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from football_analysis.config import CLUBS, DB, LEAGUES, RECENT_LEAGUES, current_season, label, seasons
from football_analysis.analytics import (
    elo_history,
    shot_coverage,
    team_match_rows,
    team_season_summaries,
    team_shot_efficiency,
)
from football_analysis.teams import display_team, team_key


MOCHA = {
    "base": "#1e1e2e", "mantle": "#181825", "crust": "#11111b",
    "surface0": "#313244", "surface1": "#45475a", "surface2": "#585b70",
    "text": "#cdd6f4", "subtext": "#bac2de", "overlay": "#6c7086",
    "mauve": "#cba6f7", "blue": "#89b4fa", "sapphire": "#74c7ec",
    "teal": "#94e2d5", "green": "#a6e3a1", "yellow": "#f9e2af",
    "peach": "#fab387", "red": "#f38ba8", "pink": "#f5c2e7",
}
ACCENT = MOCHA["mauve"]
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=MOCHA["text"]), margin=dict(l=20, r=20, t=55, b=20),
    hoverlabel=dict(bgcolor=MOCHA["surface0"], font_color=MOCHA["text"]),
    colorway=[MOCHA["mauve"], MOCHA["blue"], MOCHA["teal"], MOCHA["peach"], MOCHA["pink"], MOCHA["green"]],
)


def style_chart(fig, height=430):
    fig.update_layout(**PLOT_LAYOUT, height=height, legend_title_text="")
    fig.update_xaxes(gridcolor=MOCHA["surface0"], zeroline=False)
    fig.update_yaxes(gridcolor=MOCHA["surface0"], zeroline=False)
    return fig


def result_letter(points):
    return "W" if points == 3 else "D" if points == 1 else "L"


def load_data():
    if not DB.exists():
        return None
    try:
        with duckdb.connect(str(DB), read_only=True) as con:
            tables = {row[0] for row in con.sql("SHOW TABLES").fetchall()}
            reference = (
                con.sql("SELECT * FROM reference_standings").df()
                if "reference_standings" in tables else pd.DataFrame()
            )
            cached_elo = (
                con.sql("SELECT * FROM elo_ratings").df()
                if "elo_ratings" in tables else pd.DataFrame()
            )
            cached_shots = (
                con.sql("SELECT * FROM shot_efficiency_cache").df()
                if "shot_efficiency_cache" in tables else pd.DataFrame()
            )
            analytics_metadata = (
                con.sql("SELECT * FROM analytics_metadata").df()
                if "analytics_metadata" in tables else pd.DataFrame()
            )
            recent_matches = (
                con.sql("SELECT * FROM recent_matches").df()
                if "recent_matches" in tables else pd.DataFrame()
            )
            recent_events = (
                con.sql("SELECT * FROM recent_events").df()
                if "recent_events" in tables else pd.DataFrame()
            )
            players = (
                con.sql("SELECT * FROM players").df()
                if "players" in tables else pd.DataFrame()
            )
            player_stats = (
                con.sql("SELECT * FROM player_stats").df()
                if "player_stats" in tables else pd.DataFrame()
            )
            team_media = (
                con.sql("SELECT * FROM team_media").df()
                if "team_media" in tables else pd.DataFrame()
            )
            competition_media = (
                con.sql("SELECT * FROM competition_media").df()
                if "competition_media" in tables else pd.DataFrame()
            )
            open_players = (
                con.sql("SELECT * FROM open_players").df()
                if "open_players" in tables else pd.DataFrame()
            )
            open_player_stats = (
                con.sql("SELECT * FROM open_player_stats").df()
                if "open_player_stats" in tables else pd.DataFrame()
            )
            source_metadata = (
                con.sql("SELECT * FROM external_source_metadata").df()
                if "external_source_metadata" in tables else pd.DataFrame()
            )
            return (
                con.sql("SELECT * FROM team_seasons").df(),
                con.sql("SELECT * FROM team_matches").df(),
                con.sql("SELECT * FROM matches").df(),
                reference,
                con.sql("SELECT * FROM ingestion_runs ORDER BY fetched_at DESC").df(),
                cached_elo,
                cached_shots,
                analytics_metadata,
                recent_matches,
                recent_events,
                players,
                player_stats,
                team_media,
                competition_media,
                open_players,
                open_player_stats,
                source_metadata,
            )
    except duckdb.Error as exc:
        st.error(f"Database unavailable: {exc}")
        return None


st.set_page_config(
    page_title="Football Intelligence", page_icon="⚽", layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
    :root {--ctp-base:#1e1e2e;--ctp-mantle:#181825;--ctp-crust:#11111b;--ctp-surface0:#313244;--ctp-surface1:#45475a;--ctp-surface2:#585b70;--ctp-text:#cdd6f4;--ctp-subtext:#bac2de;--ctp-overlay:#6c7086;--ctp-mauve:#cba6f7;--ctp-blue:#89b4fa;--ctp-sapphire:#74c7ec;--ctp-teal:#94e2d5;--ctp-green:#a6e3a1;--ctp-yellow:#f9e2af;--ctp-peach:#fab387;--ctp-red:#f38ba8;--ctp-pink:#f5c2e7;}
    [data-testid="stAppViewContainer"] {background:radial-gradient(circle at 78% 0%,rgba(203,166,247,.13) 0,var(--ctp-base) 34%,var(--ctp-crust) 100%);color:var(--ctp-text);}
    [data-testid="stHeader"] {background:rgba(17,17,27,.82);}
    [data-testid="stSidebar"] {background:linear-gradient(180deg,var(--ctp-mantle),var(--ctp-crust));border-right:1px solid var(--ctp-surface0);}
    [data-testid="stMetric"] {background:linear-gradient(145deg,rgba(49,50,68,.96),rgba(24,24,37,.96));border:1px solid var(--ctp-surface1);padding:18px;border-radius:16px;box-shadow:0 10px 30px rgba(0,0,0,.24);}
    [data-testid="stMetricValue"] {color:var(--ctp-text);}
    [data-testid="stMetricDelta"] {font-size: .8rem;}
    [data-baseweb="input"],[data-baseweb="select"]>div {background:var(--ctp-surface0)!important;border-color:var(--ctp-surface1)!important;}
    [data-testid="stButton"] button,[data-testid="stDownloadButton"] button {background:var(--ctp-surface0);color:var(--ctp-text);border:1px solid var(--ctp-surface1);border-radius:10px;}
    [data-testid="stButton"] button:hover,[data-testid="stDownloadButton"] button:hover {border-color:var(--ctp-mauve);color:var(--ctp-mauve);}
    .hero {position:relative;overflow:hidden;padding:25px 28px;border-radius:22px;background:linear-gradient(110deg,rgba(203,166,247,.23),rgba(137,180,250,.16),rgba(148,226,213,.12));border:1px solid rgba(203,166,247,.42);margin-bottom:20px;box-shadow:0 24px 60px rgba(0,0,0,.28);}
    .hero::after {content:"";position:absolute;width:270px;height:270px;right:-90px;top:-150px;border-radius:50%;background:radial-gradient(circle,rgba(203,166,247,.34),transparent 68%);}
    .hero-layout {display:flex; align-items:center; justify-content:space-between; gap:24px;}
    .hero-copy {position:relative; z-index:2;}
    .hero h1 {margin: 0; font-size: 2.25rem; letter-spacing: -.04em;}
    .hero p {margin:8px 0 0;color:var(--ctp-subtext);}
    .hero-mark {position:relative;z-index:2;flex:0 0 112px;width:112px;height:112px;display:grid;place-items:center;border-radius:26px;background:rgba(17,17,27,.48);border:1px solid var(--ctp-surface1);box-shadow:inset 0 1px rgba(255,255,255,.08),0 18px 45px rgba(0,0,0,.3);animation:mark-in .65s cubic-bezier(.2,.8,.2,1) both;}
    .hero-mark img {width:82px; height:82px; object-fit:contain; filter:drop-shadow(0 10px 18px rgba(0,0,0,.32));}
    .eyebrow {color:var(--ctp-mauve);text-transform:uppercase;letter-spacing:.13em;font-weight:700;font-size:.75rem;}
    .section-note {color:var(--ctp-subtext);font-size:.9rem;margin-top:-10px;margin-bottom:10px;}
    .form-row {display:flex; gap:7px; flex-wrap:wrap; margin: 8px 0 20px;}
    .form-pill {width:31px; height:31px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-weight:800; color:white;}
    .win {background:#6c9c68}.draw {background:var(--ctp-surface2)}.loss {background:#b45c72}
    div[data-baseweb="tab-list"] {gap: 8px;}
    div[data-baseweb="tab"] {background:rgba(49,50,68,.72);border-radius:10px;padding:9px 16px;}
    div[data-baseweb="tab"][aria-selected="true"] {background:rgba(203,166,247,.18);color:var(--ctp-mauve);}
    .stDataFrame {border:1px solid var(--ctp-surface0);border-radius:12px;overflow:hidden;}
    .identity-card {display:flex;align-items:center;gap:18px;padding:18px 20px;margin:4px 0 18px;border-radius:18px;background:linear-gradient(120deg,rgba(49,50,68,.94),rgba(24,24,37,.88));border:1px solid rgba(203,166,247,.25);animation:card-in .55s ease-out both;}
    .identity-card img {width:76px; height:76px; object-fit:contain; filter:drop-shadow(0 10px 16px rgba(0,0,0,.32)); transition:transform .3s ease;}
    .identity-card:hover img {transform:scale(1.08) rotate(-2deg);}
    .identity-card h2 {margin:2px 0 3px; font-size:1.65rem;}
    .identity-card p {margin:0;color:var(--ctp-subtext);}
    .art-kicker {color:var(--ctp-mauve);font-size:.73rem;font-weight:800;text-transform:uppercase;letter-spacing:.12em;}
    .badge-rail {display:flex; gap:10px; flex-wrap:wrap; margin:10px 0 18px;}
    .badge-chip {display:flex;align-items:center;gap:8px;padding:8px 11px;border-radius:999px;background:rgba(49,50,68,.76);border:1px solid var(--ctp-surface1);color:var(--ctp-text);font-size:.82rem;animation:card-in .4s ease-out both;}
    .badge-chip img {width:25px; height:25px; object-fit:contain;}
    .player-stage {position:relative;min-height:300px;display:flex;align-items:flex-end;justify-content:center;overflow:hidden;border-radius:24px;background:radial-gradient(circle at 50% 42%,rgba(203,166,247,.28),transparent 42%),linear-gradient(165deg,var(--ctp-surface0),var(--ctp-mantle));border:1px solid rgba(203,166,247,.3);box-shadow:0 22px 55px rgba(0,0,0,.3);animation:card-in .55s ease-out both;}
    .player-stage::before {content:"";position:absolute;width:190px;height:190px;top:38px;border:1px solid rgba(203,166,247,.42);border-radius:50%;animation:ring-pulse 3.4s ease-in-out infinite;}
    .player-stage img {position:relative; z-index:2; width:94%; max-height:310px; object-fit:contain; object-position:center bottom; filter:drop-shadow(0 18px 22px rgba(0,0,0,.42)); animation:player-float 5s ease-in-out infinite;}
    .player-number {position:absolute; z-index:1; right:15px; top:7px; font-size:5.6rem; line-height:1; font-weight:900; color:rgba(255,255,255,.07); letter-spacing:-.08em;}
    .no-art {width:82px;height:82px;display:grid;place-items:center;border-radius:50%;background:linear-gradient(145deg,var(--ctp-blue),var(--ctp-mauve));color:var(--ctp-crust);font-size:1.6rem;font-weight:900;}
    .search-banner {padding:14px 18px;border-radius:16px;background:rgba(203,166,247,.1);border:1px solid rgba(203,166,247,.32);margin:0 0 18px;color:var(--ctp-text);}
    .match-strip {display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin:10px 0 20px;}
    .match-card {position:relative;overflow:hidden;padding:18px;border-radius:18px;background:linear-gradient(145deg,rgba(49,50,68,.96),rgba(24,24,37,.96));border:1px solid var(--ctp-surface1);box-shadow:0 14px 34px rgba(0,0,0,.22);}
    .match-card.live {border-color:rgba(166,227,161,.48)}
    .match-label {color:var(--ctp-mauve);text-transform:uppercase;letter-spacing:.12em;font-size:.69rem;font-weight:800;}
    .match-date {color:var(--ctp-subtext);font-size:.78rem;margin-top:3px;}
    .scoreline {display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:12px;margin:16px 0 10px;}
    .score-team {display:flex;align-items:center;gap:9px;font-weight:750;min-width:0}.score-team:last-child {justify-content:flex-end;text-align:right}.score-team img {width:36px;height:36px;object-fit:contain}.score {font-size:1.55rem;font-weight:900;color:var(--ctp-text);white-space:nowrap;}
    .match-meta {color:var(--ctp-overlay);font-size:.78rem;}
    .live-chip {display:inline-flex;align-items:center;gap:6px;padding:5px 9px;border-radius:999px;background:rgba(166,227,161,.12);color:var(--ctp-green);font-size:.73rem;font-weight:800;}
    .live-chip::before {content:"";width:7px;height:7px;border-radius:50%;background:var(--ctp-green);box-shadow:0 0 10px var(--ctp-green);}
    @keyframes card-in {from{opacity:0; transform:translateY(12px)} to{opacity:1; transform:translateY(0)}}
    @keyframes mark-in {from{opacity:0; transform:scale(.8) rotate(-6deg)} to{opacity:1; transform:scale(1) rotate(0)}}
    @keyframes player-float {0%,100%{transform:translateY(0)} 50%{transform:translateY(-7px)}}
    @keyframes ring-pulse {0%,100%{transform:scale(.92);opacity:.42} 50%{transform:scale(1.08);opacity:.8}}
    @media (prefers-reduced-motion: reduce) {.hero-mark,.identity-card,.badge-chip,.player-stage,.player-stage img,.player-stage::before{animation:none!important;transition:none!important}}
    @media (max-width:900px) {.match-strip{grid-template-columns:1fr}}
    @media (max-width:700px) {.hero-mark{width:82px;height:82px;flex-basis:82px}.hero-mark img{width:60px;height:60px}.hero h1{font-size:1.8rem}.identity-card img{width:58px;height:58px}.player-stage{min-height:240px}}
    </style>
    """,
    unsafe_allow_html=True,
)

data = load_data()
if data is None:
    st.info("The dashboard database is not available yet. Run the ingestion command from the README, then refresh this page.")
    st.stop()

(
    summaries, games, fixtures, reference_standings, runs, cached_elo,
    cached_shots, analytics_metadata, recent_matches, recent_events,
    players, player_stats, team_media, competition_media,
    open_players, open_player_stats, source_metadata,
) = data


def _safe_url(value):
    return value if isinstance(value, str) and value.startswith("https://") else ""


def team_badge(team):
    if team_media.empty or not team:
        return ""
    keys = team_media.team.map(team_key)
    rows = team_media[keys == team_key(team)]
    if rows.empty:
        return ""
    return _safe_url(rows.iloc[0].badge_url) or _safe_url(rows.iloc[0].logo_url)


def competition_badge(code):
    if competition_media.empty or not code:
        return ""
    rows = competition_media[competition_media.league_code == code]
    if rows.empty:
        return ""
    return _safe_url(rows.iloc[0].badge_url) or _safe_url(rows.iloc[0].logo_url)


def badge_rail(codes):
    chips = []
    for code in codes:
        name = RECENT_LEAGUES.get(code, code)
        url = competition_badge(code)
        visual = (
            f'<img src="{html.escape(url)}" alt="{html.escape(name)} badge">'
            if url else f'<span class="no-art" style="width:25px;height:25px;font-size:.65rem">{html.escape(name[:2].upper())}</span>'
        )
        chips.append(f'<span class="badge-chip">{visual}{html.escape(name)}</span>')
    return '<div class="badge-rail">' + "".join(chips) + "</div>"


def match_card(row, title, scheduled=False):
    home = display_team(row.home_team)
    away = display_team(row.away_team)
    home_badge = team_badge(row.home_team)
    away_badge = team_badge(row.away_team)
    home_mark = f'<img src="{html.escape(home_badge)}" alt="">' if home_badge else ""
    away_mark = f'<img src="{html.escape(away_badge)}" alt="">' if away_badge else ""
    if scheduled or pd.isna(getattr(row, "home_goals", None)):
        score = "vs"
        status = '<span class="live-chip">Scheduled</span>'
    else:
        score = f"{int(row.home_goals)}–{int(row.away_goals)}"
        status = html.escape(getattr(row, "source", "Completed"))
    match_date = pd.to_datetime(row.match_date)
    competition = RECENT_LEAGUES.get(row.league, row.league)
    return (
        f'<div class="match-card{" live" if scheduled else ""}">'
        f'<div class="match-label">{html.escape(title)}</div>'
        f'<div class="match-date">{match_date:%A, %d %B %Y} · {html.escape(competition)}</div>'
        f'<div class="scoreline"><div class="score-team">{home_mark}<span>{html.escape(home)}</span></div>'
        f'<div class="score">{score}</div>'
        f'<div class="score-team"><span>{html.escape(away)}</span>{away_mark}</div></div>'
        f'<div class="match-meta">{status}</div></div>'
    )
completed_seasons = seasons()
live_season = current_season()
expected = completed_seasons + ([live_season] if live_season not in completed_seasons else [])


def season_label(year):
    text = label(int(year))
    return f"{text} · Live" if int(year) == live_season else text


summaries = summaries[summaries.season.isin(completed_seasons)].copy()
games = games[games.season.isin(completed_seasons)].copy()
fixtures = fixtures[fixtures.season.isin(completed_seasons)].copy()
reference_standings = reference_standings[
    reference_standings.season.isin(completed_seasons)
].copy() if not reference_standings.empty else reference_standings

fixture_columns = [
    "league", "season", "match_date", "home_team", "away_team",
    "home_goals", "away_goals", "home_shots", "away_shots", "home_sot", "away_sot",
]
current_fixtures = recent_matches[
    recent_matches.league.isin(RECENT_LEAGUES) & (recent_matches.season == live_season)
][fixture_columns].copy() if not recent_matches.empty else pd.DataFrame(columns=fixture_columns)
current_games = team_match_rows(current_fixtures)
current_summaries = team_season_summaries(current_games)
if not current_fixtures.empty:
    fixtures = pd.concat([fixtures, current_fixtures], ignore_index=True)
    games = pd.concat([games, current_games], ignore_index=True)
    summaries = pd.concat([summaries, current_summaries], ignore_index=True)

spotlight_columns = [
    "league", "season", "match_date", "home_team", "away_team",
    "home_goals", "away_goals", "source", "fetched_at",
]
spotlight_matches = recent_matches[
    recent_matches.league.isin(RECENT_LEAGUES) & (recent_matches.season == live_season)
][spotlight_columns].copy() if not recent_matches.empty else pd.DataFrame(columns=spotlight_columns)
event_results = recent_events[
    recent_events.league.isin(RECENT_LEAGUES)
    & (recent_events.season == live_season)
    & (recent_events.event_kind == "past")
    & recent_events.home_goals.notna()
    & recent_events.away_goals.notna()
][spotlight_columns].copy() if not recent_events.empty else pd.DataFrame(columns=spotlight_columns)
spotlight_matches = pd.concat([spotlight_matches, event_results], ignore_index=True)
if not spotlight_matches.empty:
    spotlight_matches["home_key"] = spotlight_matches.home_team.map(team_key)
    spotlight_matches["away_key"] = spotlight_matches.away_team.map(team_key)
    spotlight_matches = spotlight_matches.sort_values(["match_date", "fetched_at"]).drop_duplicates(
        ["league", "match_date", "home_key", "away_key"], keep="last",
    )
upcoming_events = recent_events[
    recent_events.league.isin(RECENT_LEAGUES)
    & (recent_events.season == live_season)
    & (recent_events.event_kind == "next")
].sort_values("match_date").copy() if not recent_events.empty else pd.DataFrame()

completed_coverage = summaries[
    summaries.season.isin(completed_seasons)
][["league", "season"]].drop_duplicates()
coverage = summaries[["league", "season"]].drop_duplicates()
if summaries.empty:
    st.info("No complete seasons are loaded yet. Run ingestion, then return to this page.")
    st.stop()

elite_available = [team for team in CLUBS if team in set(summaries.team)]
available_competitions = [code for code in RECENT_LEAGUES if code in set(summaries.league)]


elo = cached_elo if not cached_elo.empty else elo_history(fixtures)
shot_coverage_frame = shot_coverage(fixtures)
shot_efficiency = cached_shots if not cached_shots.empty else team_shot_efficiency(games)
season_elo = (
    elo.sort_values("match_date")
    .groupby(["league", "season", "team"], as_index=False)
    .tail(1)
)

with st.sidebar:
    st.markdown("## ⚽ Football Intelligence")
    st.caption("Search, compare and explore")
    platform_search = st.text_input(
        "Search platform", placeholder="Player, club or competition…",
        help="Search all featured clubs, competitions and the complete player snapshot.",
    ).strip()
    st.divider()
    analysis_mode = st.radio(
        "Analysis mode", ["Compare clubs", "Club focus", "Competition view"],
        captions=["Benchmark elite teams", "One club in depth", "Full league standings"],
    )
    st.divider()
    year_range = st.select_slider(
        "Season range", options=expected, value=(expected[0], expected[-1]),
        format_func=season_label, help="Choose completed seasons and the live 2026/27 season.",
    )
    year_filter = list(range(year_range[0], year_range[1] + 1))
    if analysis_mode == "Competition view":
        competition_focus = st.selectbox(
            "Competition", options=available_competitions,
            format_func=lambda code: RECENT_LEAGUES[code],
        )
        league_filter = [competition_focus]
        chart_limit = st.selectbox(
            "Overview clubs", options=[5, 10, "All"], index=1,
            format_func=lambda value: "All clubs" if value == "All" else f"Top {value}",
            help="League tables remain complete; this limit keeps charts readable.",
        )
    else:
        league_filter = st.multiselect(
            "Competitions", options=available_competitions,
            default=[code for code in LEAGUES if code in available_competitions],
            format_func=lambda code: RECENT_LEAGUES[code], placeholder="Select competitions",
        )
        chart_limit = None
    all_available_clubs = sorted(
        summaries.loc[
            summaries.league.isin(league_filter) & summaries.season.isin(year_filter),
            "team",
        ].unique(),
        key=display_team,
    )
    available_clubs = [team for team in elite_available if team in all_available_clubs]
    if analysis_mode == "Club focus":
        selected_club = st.selectbox(
            "Primary club", available_clubs,
            format_func=lambda team: CLUBS[team],
        ) if available_clubs else None
        compare_clubs = [selected_club] if selected_club else []
    elif analysis_mode == "Compare clubs":
        compare_clubs = st.multiselect(
            "Elite clubs", available_clubs,
            default=available_clubs[: min(6, len(available_clubs))],
            format_func=lambda team: CLUBS[team], max_selections=8,
            placeholder="Choose up to 8 clubs",
        )
        selected_club = compare_clubs[0] if compare_clubs else None
    else:
        available_clubs = all_available_clubs
        latest_competition_year = max(
            summaries.loc[
                summaries.league.isin(league_filter) & summaries.season.isin(year_filter),
                "season",
            ]
        )
        latest_competition_table = summaries[
            summaries.league.isin(league_filter)
            & (summaries.season == latest_competition_year)
        ].sort_values(["points", "goal_difference", "goals_for"], ascending=False)
        limit = len(latest_competition_table) if chart_limit == "All" else int(chart_limit)
        compare_clubs = latest_competition_table.head(limit).team.tolist()
        selected_club = compare_clubs[0] if compare_clubs else None
    form_window = st.slider("Recent form window", 3, 10, 5)
    st.divider()
    st.caption("Five completed seasons + live 2026/27 · Free public data")

selected = summaries[
    summaries.league.isin(league_filter) & summaries.season.isin(year_filter)
    & summaries.team.isin(compare_clubs)
].copy()
selected_games = games[
    games.league.isin(league_filter) & games.season.isin(year_filter)
    & games.team.isin(compare_clubs)
].copy()

if analysis_mode == "Club focus":
    hero_title = display_team(selected_club)
    hero_eyebrow = "Club performance room"
    hero_text = "Follow form, strength, scoring and league results across five completed seasons plus live 2026/27."
    hero_image = team_badge(selected_club)
elif analysis_mode == "Competition view":
    hero_title = RECENT_LEAGUES[league_filter[0]]
    hero_eyebrow = "Competition intelligence"
    hero_text = "Explore the complete table, season trends and every club in the selected domestic league."
    hero_image = competition_badge(league_filter[0])
else:
    hero_title = "Football Intelligence"
    hero_eyebrow = "European club performance lab"
    hero_text = "Compare elite clubs across five completed seasons and the live 2026/27 campaign."
    hero_image = team_badge(selected_club)

hero_mark = (
    f'<div class="hero-mark"><img src="{html.escape(hero_image)}" alt="{html.escape(hero_title)} emblem"></div>'
    if hero_image else ""
)
st.markdown(
    f"""
    <div class="hero hero-layout">
      <div class="hero-copy">
        <div class="eyebrow">{html.escape(hero_eyebrow)}</div>
        <h1>{html.escape(hero_title)}</h1>
        <p>{html.escape(hero_text)}</p>
      </div>
      {hero_mark}
    </div>
    """,
    unsafe_allow_html=True,
)

search_term = platform_search.casefold()
player_hits = pd.DataFrame()
club_hits = []
competition_hits = []
if search_term:
    if not open_players.empty:
        player_hits = open_players[
            open_players.player.str.casefold().str.contains(search_term, regex=False, na=False)
            | open_players.team.map(display_team).str.casefold().str.contains(search_term, regex=False, na=False)
            | open_players.position.str.casefold().str.contains(search_term, regex=False, na=False)
            | open_players.nationality.str.casefold().str.contains(search_term, regex=False, na=False)
        ].copy()
    club_hits = [
        (code, name) for code, name in CLUBS.items()
        if search_term in name.casefold()
    ]
    competition_hits = [
        (code, name) for code, name in RECENT_LEAGUES.items()
        if search_term in name.casefold()
    ]
    total_hits = len(player_hits) + len(club_hits) + len(competition_hits)
    preview = [*player_hits.player.head(3).tolist(), *[name for _, name in club_hits[:2]], *[name for _, name in competition_hits[:2]]]
    detail = " · ".join(preview) if preview else "Try another spelling or a broader term."
    st.markdown(
        f'<div class="search-banner"><b>{total_hits} search result{"s" if total_hits != 1 else ""}</b> for '
        f'“{html.escape(platform_search)}”<br><span>{html.escape(detail)}</span></div>',
        unsafe_allow_html=True,
    )

if not league_filter:
    st.info("Select at least one competition to begin.")
    st.stop()
if analysis_mode != "Competition view" and selected.empty:
    st.info("Choose at least one club to begin the comparison.")
    st.stop()

if analysis_mode == "Competition view":
    hero_rows = summaries[summaries.league.isin(league_filter) & summaries.season.isin(year_filter)]
    hero_games = games[games.league.isin(league_filter) & games.season.isin(year_filter)]
else:
    hero_rows, hero_games = selected, selected_games

best_row = hero_rows.loc[hero_rows.points_per_game.idxmax()]
goals, played = int(hero_rows.goals_for.sum()), int(hero_rows.played.sum())
latest_date = pd.to_datetime(hero_games.match_date).max()
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Clubs covered" if analysis_mode == "Competition view" else "Selected clubs", hero_rows.team.nunique())
m2.metric("Matches analysed", f"{played if analysis_mode != 'Competition view' else played // 2:,}")
m3.metric("Goals scored", f"{goals:,}")
m4.metric("Average PPG", f"{hero_rows.points.sum()/played:.2f}")
m5.metric("Peak season", f"{best_row.points_per_game:.2f}", f"{best_row.team} · {season_label(best_row.season)}")
if analysis_mode == "Competition view":
    st.caption(f"Results through {latest_date:%d %B %Y}. Competition totals include every club in the selected league.")
else:
    st.caption(f"Results through {latest_date:%d %B %Y}. Each selected club's performance is counted independently.")

overview, standings_tab, club_lab, shots_tab, matches_tab, players_tab, quality = st.tabs(
    [
        "Overview", "League tables", "Club lab", "Shot lab", "Match explorer", "Players", "Data quality",
    ]
)

with overview:
    if analysis_mode == "Competition view":
        overview_rows = summaries[
            summaries.league.isin(league_filter) & summaries.season.isin(year_filter)
            & summaries.team.isin(compare_clubs)
        ].copy()
        overview_rows["Club"] = overview_rows.team.map(display_team)
        st.caption(
            f"Charts show {len(compare_clubs)} clubs from the {season_label(latest_competition_year)} table. "
            "The League tables tab still shows every club."
        )
    else:
        overview_rows = selected.copy()
        overview_rows["Club"] = overview_rows.team.map(display_team)
    overview_rows["Season"] = overview_rows.season.map(season_label)

    live_focus = selected_club
    if live_season in year_filter and live_focus and not current_summaries.empty:
        live_key = team_key(live_focus)
        live_rows = current_summaries[
            current_summaries.team.map(team_key).eq(live_key)
            & current_summaries.league.isin(league_filter)
        ]
        live_results = spotlight_matches[
            spotlight_matches.home_key.eq(live_key) | spotlight_matches.away_key.eq(live_key)
        ].sort_values("match_date", ascending=False) if not spotlight_matches.empty else pd.DataFrame()
        live_upcoming = upcoming_events[
            upcoming_events.home_team.map(team_key).eq(live_key)
            | upcoming_events.away_team.map(team_key).eq(live_key)
        ] if not upcoming_events.empty else pd.DataFrame()
        if not live_rows.empty or not live_results.empty:
            st.markdown(f"#### {season_label(live_season)} · {display_team(live_focus)}")
            if not live_rows.empty:
                live_row = live_rows.iloc[0]
                lc1, lc2, lc3, lc4 = st.columns(4)
                lc1.metric("Played", int(live_row.played))
                lc2.metric("W–D–L", f"{int(live_row.wins)}–{int(live_row.draws)}–{int(live_row.losses)}")
                lc3.metric("Points / match", f"{live_row.points_per_game:.2f}")
                lc4.metric("Goal difference", f"{int(live_row.goal_difference):+d}")
            cards = [
                match_card(row, "Latest completed match" if index == 0 else "Previous match")
                for index, row in enumerate(live_results.head(2).itertuples(index=False))
            ]
            if not live_upcoming.empty:
                cards.append(match_card(live_upcoming.iloc[0], "Next listed fixture", scheduled=True))
            if cards:
                st.markdown('<div class="match-strip">' + "".join(cards) + "</div>", unsafe_allow_html=True)
            st.caption("2026/27 values are live and partial; they update from completed free-source results.")
    left, right = st.columns([1.35, 1])
    with left:
        trend = px.line(
            overview_rows.sort_values("season"), x="Season", y="points_per_game",
            color="Club", markers=True, title="Performance over time",
            labels={"points_per_game": "Points per game"},
        )
        trend.update_traces(line=dict(width=3), marker=dict(size=8))
        st.plotly_chart(style_chart(trend), width="stretch")
    with right:
        matrix = overview_rows.pivot_table(index="Club", columns="Season", values="points_per_game")
        heat = px.imshow(
            matrix, text_auto=".2f",
            color_continuous_scale=[[0, "#19283c"], [.5, "#267f78"], [1, ACCENT]],
            title="Season strength map", aspect="auto",
        )
        heat.update_coloraxes(showscale=False)
        st.plotly_chart(style_chart(heat), width="stretch")

    totals = overview_rows.groupby("Club", as_index=False).agg(
        played=("played", "sum"), points=("points", "sum"),
        goals_for=("goals_for", "sum"), goals_against=("goals_against", "sum"),
    )
    totals["Goals / match"] = totals.goals_for / totals.played
    totals["Conceded / match"] = totals.goals_against / totals.played
    totals["PPG"] = totals.points / totals.played
    scatter = px.scatter(
        totals, x="Goals / match", y="Conceded / match", size="PPG", color="PPG",
        hover_name="Club", text="Club",
        color_continuous_scale=["#ff6b7a", "#f7c66d", ACCENT],
        title="Attacking output vs defensive control",
    )
    scatter.update_traces(
        textposition="top center",
        marker=dict(sizemin=9, line=dict(width=1, color="rgba(255,255,255,.5)")),
    )
    scatter.update_yaxes(autorange="reversed")
    st.plotly_chart(style_chart(scatter, 500), width="stretch")

    elo_rows = season_elo[
        season_elo.league.isin(league_filter) & season_elo.season.isin(year_filter)
        & season_elo.team.isin(overview_rows.team.unique())
    ].copy()
    elo_rows["Club"] = elo_rows.team.map(display_team)
    elo_rows["Season"] = elo_rows.season.map(season_label)
    elo_chart = px.line(
        elo_rows.sort_values("season"), x="Season", y="post_elo", color="Club",
        markers=True, title="Opponent-adjusted season-end Elo",
        labels={"post_elo": "Elo rating"},
    )
    elo_chart.update_traces(line=dict(width=3), marker=dict(size=8))
    st.plotly_chart(style_chart(elo_chart), width="stretch")
    st.caption("Elo is calculated chronologically from domestic league matches. Same-day fixtures use the same pre-match rating snapshot.")
    if len(league_filter) > 1:
        st.caption("Absolute Elo levels are calibrated within each domestic competition. Use cross-league Elo to compare trends, not exact strength gaps.")

with standings_tab:
    st.subheader("Reconstructed league table")
    st.markdown(
        '<div class="section-note">Choose one competition and season. Rankings use match-derived points and goal difference.</div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    table_league = c1.selectbox(
        "Competition", league_filter, format_func=lambda code: RECENT_LEAGUES[code], key="table_league",
    )
    valid_years = [
        year for year in sorted(summaries.loc[summaries.league == table_league, "season"].unique(), reverse=True)
        if year in year_filter
    ]
    table_year = c2.selectbox("Season", valid_years, format_func=season_label, key="table_year")
    st.markdown(badge_rail([table_league]), unsafe_allow_html=True)
    table = summaries[(summaries.league == table_league) & (summaries.season == table_year)].copy()
    table = table.sort_values(["points", "goal_difference", "goals_for"], ascending=False).reset_index(drop=True)
    table.insert(0, "Rank", range(1, len(table) + 1))
    table["Club"] = table.team.map(display_team)
    table["Form"] = table.team.map(
        lambda team: " ".join(
            games[
                (games.league == table_league) & (games.season == table_year)
                & (games.team == team)
            ].sort_values("match_date").tail(form_window).points.map(result_letter)
        )
    )
    st.markdown("#### Results-derived table")
    st.dataframe(
        table[[
            "Rank", "Club", "played", "wins", "draws", "losses", "goals_for",
            "goals_against", "goal_difference", "points", "Form",
        ]],
        hide_index=True, width="stretch",
        column_config={
            "played": st.column_config.NumberColumn("P"),
            "wins": st.column_config.NumberColumn("W"),
            "draws": st.column_config.NumberColumn("D"),
            "losses": st.column_config.NumberColumn("L"),
            "goals_for": st.column_config.NumberColumn("GF"),
            "goals_against": st.column_config.NumberColumn("GA"),
            "goal_difference": st.column_config.NumberColumn("GD"),
            "points": st.column_config.ProgressColumn(
                "Pts", min_value=0, max_value=int(table.points.max()),
            ),
        },
    )
    if table_year == live_season:
        st.caption("Live partial table from completed 2026/27 results. Rankings can change after every match.")
    else:
        st.caption("Results-derived points exclude administrative deductions and official competition-specific tiebreakers.")
    st.markdown("#### External reference table")
    reference = reference_standings[
        (reference_standings.league == table_league)
        & (reference_standings.season == table_year)
    ].sort_values("rank") if not reference_standings.empty else pd.DataFrame()
    if reference.empty:
        message = (
            "External reference validation is added after the season is complete."
            if table_year == live_season else
            "No external reference table is cached for this competition and season."
        )
        st.info(message)
    else:
        reference_display = reference[[
            "rank", "team", "played", "points", "goal_difference", "form", "description"
        ]].copy()
        reference_display["club_key"] = reference_display.team.map(team_key)
        derived_reference = table[["Rank", "team", "points", "goal_difference"]].copy()
        derived_reference["club_key"] = derived_reference.team.map(team_key)
        reference_display = reference_display.merge(
            derived_reference, on="club_key", how="left", suffixes=("_reference", "_results")
        )
        reference_display["Club"] = reference_display.team_reference.map(display_team)
        reference_display["Point adjustment"] = (
            reference_display.points_reference - reference_display.points_results
        )
        reference_display["Rank difference"] = (
            reference_display["rank"] - reference_display["Rank"]
        )
        reference_display = reference_display.rename(columns={
            "rank": "Reference rank", "played": "Reference P",
            "points_reference": "Reference points", "points_results": "Results points",
            "goal_difference_reference": "Reference GD",
            "goal_difference_results": "Results GD", "form": "Reference form",
            "description": "Qualification",
        })[[
            "Reference rank", "Club", "Reference P", "Reference points",
            "Results points", "Point adjustment", "Reference GD", "Results GD",
            "Rank difference", "Reference form", "Qualification",
        ]]
        st.dataframe(reference_display, hide_index=True, width="stretch")
        adjustments = int((reference_display["Point adjustment"].fillna(0) != 0).sum())
        st.caption(
            "TheSportsDB is a crowd-sourced top-five reference feed. "
            f"Reference − results points exposes administrative adjustments ({adjustments} in this view)."
        )

with club_lab:
    if analysis_mode == "Club focus":
        focus_club = selected_club
        st.caption(f"Following the primary club selection: {display_team(focus_club)}")
    else:
        focus_club = st.selectbox(
            "Club", available_clubs,
            index=available_clubs.index(selected_club) if selected_club in available_clubs else 0,
            format_func=display_team, key=f"lab_club_{analysis_mode}",
        )
    club_games = games[
        (games.team == focus_club) & games.season.isin(year_filter)
        & games.league.isin(league_filter)
    ].sort_values("match_date").copy()
    focus_badge = team_badge(focus_club)
    focus_leagues = sorted(club_games.league.unique())
    badge_visual = (
        f'<img src="{html.escape(focus_badge)}" alt="{html.escape(display_team(focus_club))} badge">'
        if focus_badge else f'<span class="no-art">{html.escape(display_team(focus_club)[:2].upper())}</span>'
    )
    st.markdown(
        f'<div class="identity-card">{badge_visual}<div><span class="art-kicker">Club focus</span>'
        f'<h2>{html.escape(display_team(focus_club))}</h2>'
        f'<p>{html.escape(" · ".join(RECENT_LEAGUES[code] for code in focus_leagues))}</p></div></div>',
        unsafe_allow_html=True,
    )
    recent = club_games.tail(form_window)
    form_html = "".join(
        f'<span class="form-pill {"win" if p == 3 else "draw" if p == 1 else "loss"}">{result_letter(p)}</span>'
        for p in recent.points
    )
    st.markdown(
        f"### {display_team(focus_club)} <span style='color:#8fa6bd;font-size:1rem'>recent form</span>",
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="form-row">{form_html}</div>', unsafe_allow_html=True)
    club_elo = elo[(elo.team == focus_club) & elo.season.isin(year_filter)].sort_values("match_date")
    current_elo = club_elo.iloc[-1].post_elo
    elo_delta = current_elo - club_elo.iloc[0].pre_elo
    f1, f2, f3, f4, f5 = st.columns(5)
    f1.metric(f"Last {len(recent)} PPG", f"{recent.points.mean():.2f}")
    f2.metric("Win rate", f"{100*(club_games.points == 3).mean():.1f}%")
    f3.metric("Goal difference", f"{int((club_games.gf-club_games.ga).sum()):+d}")
    f4.metric("Clean-sheet rate", f"{100*(club_games.ga == 0).mean():.1f}%")
    f5.metric("Current Elo", f"{current_elo:.0f}", f"{elo_delta:+.0f} in range")

    club_games["Rolling PPG"] = club_games.groupby(
        ["league", "season"], sort=False
    )["points"].transform(lambda values: values.rolling(form_window, min_periods=1).mean())
    form_chart = px.line(
        club_games, x="match_date", y="Rolling PPG", color="season",
        title=f"Rolling {form_window}-match form", labels={"match_date": "Match date"},
    )
    form_chart.add_hline(
        y=2, line_dash="dot", line_color="rgba(255,255,255,.35)", annotation_text="2.0 PPG",
    )
    st.plotly_chart(style_chart(form_chart), width="stretch")

    radar_source = summaries[
        summaries.season.isin(year_filter) & summaries.league.isin(league_filter)
    ].copy()
    radar_source["clean_sheet_rate"] = radar_source.clean_sheets / radar_source.played
    radar_metrics = ["goals_per_game", "points_per_game", "win_rate", "clean_sheet_rate"]
    benchmark = radar_source.groupby("team", as_index=False)[radar_metrics].mean()
    focus_index = benchmark.index[benchmark.team == focus_club][0]
    values = [float(benchmark[metric].rank(pct=True).loc[focus_index] * 100) for metric in radar_metrics]
    radar = go.Figure(go.Scatterpolar(
        r=values + values[:1],
        theta=["Scoring", "Points", "Win rate", "Clean sheets", "Scoring"],
        fill="toself", line_color=ACCENT, fillcolor="rgba(87,230,187,.25)",
    ))
    radar.update_layout(
        title="Selected-competition percentile profile", showlegend=False,
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 100], gridcolor="rgba(255,255,255,.12)"),
            angularaxis=dict(gridcolor="rgba(255,255,255,.12)"),
        ),
    )
    st.plotly_chart(style_chart(radar), width="stretch")

with shots_tab:
    st.subheader("Shot quality and efficiency")
    st.markdown(
        '<div class="section-note">Metrics appear only when at least 95% of a club-season has complete shots and shots-on-target fields.</div>',
        unsafe_allow_html=True,
    )
    coverage_rows = shot_coverage_frame[
        shot_coverage_frame.league.isin(league_filter)
        & shot_coverage_frame.season.isin(year_filter)
    ].copy()
    coverage_rows["Competition"] = coverage_rows.league.map(RECENT_LEAGUES)
    coverage_rows["Season"] = coverage_rows.season.map(season_label)
    gated = shot_efficiency[
        shot_efficiency.league.isin(league_filter)
        & shot_efficiency.season.isin(year_filter)
        & shot_efficiency.team.isin(compare_clubs if compare_clubs else elite_available)
    ].copy()
    if gated.empty:
        st.info("No selected club-season passes the 95% shot-data coverage gate.")
    else:
        gated["Club"] = gated.team.map(CLUBS).fillna(gated.team)
        gated["Season"] = gated.season.map(season_label)
        s1, s2, s3 = st.columns(3)
        s1.metric("Eligible club-seasons", len(gated))
        s2.metric("Average shot coverage", f"{gated.coverage_pct.mean():.1f}%")
        s3.metric("Average shots / match", f"{gated.shots_per_match.mean():.1f}")
        efficiency_chart = px.scatter(
            gated, x="shot_accuracy_pct", y="goals_per_shot_pct",
            size="shots_per_match", color="Club", symbol="Season",
            hover_name="Club", hover_data={"coverage_pct": ":.1f", "Season": True},
            title="Accuracy vs finishing efficiency",
            labels={
                "shot_accuracy_pct": "Shots on target / shots (%)",
                "goals_per_shot_pct": "Goals / shots (%)",
            },
        )
        st.plotly_chart(style_chart(efficiency_chart, 500), width="stretch")
        volume = gated.groupby("Club", as_index=False).agg(
            shots_per_match=("shots_per_match", "mean"),
            goals_per_sot_pct=("goals_per_sot_pct", "mean"),
        ).sort_values("shots_per_match")
        volume_chart = px.bar(
            volume, x="shots_per_match", y="Club", orientation="h",
            color="goals_per_sot_pct", color_continuous_scale=["#52718f", ACCENT],
            title="Shot volume and on-target conversion",
            labels={"shots_per_match": "Shots per match", "goals_per_sot_pct": "Goals / SOT (%)"},
        )
        st.plotly_chart(style_chart(volume_chart), width="stretch")
    with st.expander("View source coverage by competition and season"):
        coverage_matrix = coverage_rows.pivot(
            index="Competition", columns="Season", values="coverage_pct"
        )
        st.dataframe(
            coverage_matrix, width="stretch",
            column_config={season: st.column_config.ProgressColumn(season, min_value=0, max_value=100, format="%.1f%%") for season in coverage_matrix.columns},
        )

with matches_tab:
    st.subheader("Match explorer")
    e1, e2, e3 = st.columns([1.2, 1, 1])
    if analysis_mode == "Club focus":
        match_club = selected_club
        e1.metric("Club", display_team(match_club))
    else:
        match_club = e1.selectbox(
            "Club", available_clubs,
            index=available_clubs.index(selected_club) if selected_club in available_clubs else 0,
            format_func=display_team, key=f"match_club_{analysis_mode}",
        )
    opponent_options = sorted(games.loc[
        (games.team == match_club) & games.season.isin(year_filter)
        & games.league.isin(league_filter), "opponent"
    ].unique(), key=display_team)
    opponent = e2.selectbox(
        "Opponent", ["All opponents"] + opponent_options,
        format_func=lambda name: name if name == "All opponents" else display_team(name),
        key=f"opponent_{analysis_mode}",
    )
    venue = e3.segmented_control("Venue", ["All", "Home", "Away"], default="All")
    rows = games[
        (games.team == match_club) & games.season.isin(year_filter)
        & games.league.isin(league_filter)
    ].copy()
    if opponent != "All opponents":
        rows = rows[rows.opponent == opponent]
    if venue != "All":
        rows = rows[rows.venue == venue]
    rows = rows.sort_values("match_date", ascending=False)
    rows["result"] = rows.points.map(result_letter)
    rows["score"] = rows.gf.astype(str) + "–" + rows.ga.astype(str)
    if rows.empty:
        st.info("No matches fit these filters.")
    else:
        r1, r2, r3 = st.columns(3)
        r1.metric("Matches", len(rows))
        r2.metric("Points per game", f"{rows.points.mean():.2f}")
        r3.metric("Goal difference", f"{int((rows.gf - rows.ga).sum()):+d}")
        display = rows[[
            "match_date", "season", "venue", "opponent", "score", "result",
            "shots", "shots_on_target",
        ]].copy()
        display["opponent"] = display.opponent.map(display_team)
        display["season"] = display.season.map(season_label)
        st.dataframe(
            display, hide_index=True, width="stretch",
            column_config={
                "match_date": "Date", "season": "Season", "venue": "Venue",
                "opponent": "Opponent", "score": "Score", "result": "Result",
                "shots": "Shots", "shots_on_target": "On target",
            },
        )
        st.download_button(
            "Download this match view", display.to_csv(index=False),
            f"{match_club.lower().replace(' ', '_')}_matches.csv", "text/csv",
        )

with players_tab:
    st.subheader("Player explorer")
    st.markdown(
        '<div class="section-note">All tracked 2025/26 player records for the 12 featured clubs, with domestic and European appearance totals across five completed seasons.</div>',
        unsafe_allow_html=True,
    )
    if open_players.empty:
        st.info("The full player snapshot has not been synchronized yet. Run football-sync-open-players, then refresh.")
    else:
        player_clubs = sorted(open_players.team.dropna().unique(), key=display_team)
        preferred_club = selected_club if selected_club in player_clubs else player_clubs[0]
        pc1, pc2, pc3 = st.columns([1, 1, 1.4])
        player_club = pc1.selectbox(
            "Squad", player_clubs, index=player_clubs.index(preferred_club),
            format_func=display_team,
        )
        club_players = open_players[open_players.team == player_club].copy()
        position_options = sorted(value for value in club_players.position.dropna().unique() if value)
        position_filter = pc2.multiselect("Positions", position_options, placeholder="All positions")
        name_search = pc3.text_input("Find a player", placeholder="Type a name…").strip().casefold()
        filtered_players = club_players.copy()
        if position_filter:
            filtered_players = filtered_players[filtered_players.position.isin(position_filter)]
        if name_search:
            filtered_players = filtered_players[
                filtered_players.player.str.casefold().str.contains(name_search, regex=False, na=False)
            ]

        as_of = pd.to_datetime(club_players.data_as_of).max()
        births = pd.to_datetime(club_players.date_born, errors="coerce")
        ages = (as_of - births).dt.days / 365.2425
        squad_stats = open_player_stats[open_player_stats.team == player_club].groupby(
            "player_id", as_index=False
        ).agg(
            appearances=("appearances", "sum"), goals=("goals", "sum"),
            assists=("assists", "sum"), minutes=("minutes_played", "sum"),
        ) if not open_player_stats.empty else pd.DataFrame()
        sq1, sq2, sq3, sq4 = st.columns(4)
        sq1.metric("Tracked players", len(club_players))
        sq2.metric("Average age", f"{ages.mean():.1f}" if ages.notna().any() else "—")
        sq3.metric("Nationalities", club_players.nationality.replace("", pd.NA).nunique())
        total_value = club_players.market_value_eur.fillna(0).sum()
        sq4.metric("Squad value", f"€{total_value / 1_000_000:.0f}m" if total_value else "—")

        if filtered_players.empty:
            st.info("No player matches these filters.")
        else:
            filtered_players = filtered_players.sort_values(["position", "player"])
            player_id = st.selectbox(
                "Selected player", filtered_players.player_id.tolist(),
                format_func=lambda value: filtered_players.loc[
                    filtered_players.player_id == value, "player"
                ].iloc[0],
            )
            profile = filtered_players[filtered_players.player_id == player_id].iloc[0]
            legacy = players[
                (players.player.map(team_key) == team_key(profile.player))
                & (players.team.map(team_key) == team_key(profile.team))
            ] if not players.empty else pd.DataFrame()
            legacy_profile = legacy.iloc[0] if not legacy.empty else None
            legacy_image = "" if legacy_profile is None else (
                _safe_url(legacy_profile.cutout_url) or _safe_url(legacy_profile.thumb_url)
            )
            image_url = legacy_image or _safe_url(profile.image_url)
            shirt_number = "" if legacy_profile is None else str(legacy_profile.shirt_number or "")
            image_column, profile_column = st.columns([1, 3])
            with image_column:
                if image_url:
                    st.markdown(
                        f'<div class="player-stage"><span class="player-number">{html.escape(shirt_number)}</span>'
                        f'<img src="{html.escape(image_url)}" alt="Portrait of {html.escape(str(profile.player))}"></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    initials = "".join(part[0] for part in str(profile.player).split()[:2]).upper()
                    st.markdown(
                        f'<div class="player-stage"><span class="no-art">{html.escape(initials)}</span></div>',
                        unsafe_allow_html=True,
                    )
            with profile_column:
                st.markdown(f"### {profile.player}")
                birth = pd.to_datetime(profile.date_born, errors="coerce")
                age = "Unknown" if pd.isna(birth) else str(int((as_of - birth).days / 365.2425))
                pp1, pp2, pp3, pp4 = st.columns(4)
                pp1.metric("Position", profile.position or "Unknown")
                pp2.metric("Role", profile.sub_position or "Unknown")
                pp3.metric("Nationality", profile.nationality or "Unknown")
                pp4.metric("Age at snapshot", age)
                detail_parts = []
                if pd.notna(profile.height_cm):
                    detail_parts.append(f"{int(profile.height_cm)} cm")
                if profile.foot:
                    detail_parts.append(f"{profile.foot.title()}-footed")
                if pd.notna(profile.market_value_eur):
                    detail_parts.append(f"€{profile.market_value_eur / 1_000_000:.1f}m market value")
                if detail_parts:
                    st.caption(" · ".join(detail_parts))

            stats = open_player_stats[
                (open_player_stats.player_id == player_id)
                & open_player_stats.season.isin(year_filter)
            ].copy()
            if stats.empty:
                st.info("No appearance rows were published for this player in the selected seasons.")
            else:
                stats["Competition"] = stats.competition.str.replace("-", " ").str.title()
                competition_options = sorted(stats.Competition.unique())
                chosen_competitions = st.multiselect(
                    "Player competitions", competition_options, default=competition_options,
                    help="Includes domestic leagues, cups and UEFA competitions present in the open dataset.",
                )
                stats = stats[stats.Competition.isin(chosen_competitions)]
                totals = stats[["appearances", "goals", "assists", "minutes_played"]].sum()
                ps1, ps2, ps3, ps4 = st.columns(4)
                ps1.metric("Appearances", f"{int(totals.appearances):,}")
                ps2.metric("Goals", f"{int(totals.goals):,}")
                ps3.metric("Assists", f"{int(totals.assists):,}")
                ps4.metric("Minutes", f"{int(totals.minutes_played):,}")
                by_season = stats.groupby("season", as_index=False).agg(
                    appearances=("appearances", "sum"), goals=("goals", "sum"),
                    assists=("assists", "sum"), minutes=("minutes_played", "sum"),
                )
                by_season["Season"] = by_season.season.map(season_label)
                chart_values = by_season.melt(
                    id_vars="Season", value_vars=["goals", "assists"],
                    var_name="Metric", value_name="Total",
                )
                player_chart = px.bar(
                    chart_values, x="Season", y="Total", color="Metric", barmode="group",
                    title="Goals and assists by season",
                    color_discrete_map={"goals": ACCENT, "assists": "#6f9df5"},
                )
                left, right = st.columns([1.25, 1])
                left.plotly_chart(style_chart(player_chart, 360), width="stretch")
                right.dataframe(
                    by_season[["Season", "appearances", "goals", "assists", "minutes"]],
                    hide_index=True, width="stretch",
                    column_config={
                        "appearances": "Apps", "goals": "Goals", "assists": "Assists",
                        "minutes": st.column_config.NumberColumn("Minutes", format="%d"),
                    },
                )
                with st.expander("Competition detail"):
                    st.dataframe(
                        stats[["season", "Competition", "appearances", "goals", "assists", "minutes_played", "yellow_cards", "red_cards"]].sort_values(["season", "Competition"], ascending=[False, True]),
                        hide_index=True, width="stretch",
                        column_config={"season": "Season start", "minutes_played": "Minutes", "yellow_cards": "Yellow", "red_cards": "Red"},
                    )

        st.markdown("#### Full tracked squad")
        st.caption("Totals cover each player's published appearances across the selected completed seasons. The open source has no 2026/27 player rows yet.")
        squad_table = club_players.merge(squad_stats, on="player_id", how="left") if not squad_stats.empty else club_players
        for column in ["appearances", "goals", "assists", "minutes"]:
            if column not in squad_table:
                squad_table[column] = 0
        squad_table["Club"] = squad_table.team.map(display_team)
        st.dataframe(
            squad_table[["image_url", "player", "position", "sub_position", "nationality", "appearances", "goals", "assists", "minutes"]].sort_values(["position", "player"]),
            hide_index=True, width="stretch",
            column_config={
                "image_url": st.column_config.ImageColumn(""), "player": "Player",
                "position": "Position", "sub_position": "Role", "nationality": "Nationality",
                "appearances": "Apps", "goals": "Goals", "assists": "Assists", "minutes": "Minutes",
            },
        )
        st.caption(
            f"{len(club_players)} tracked player records for {display_team(player_club)} · "
            f"match data through {as_of:%d %B %Y} · Source: Transfermarkt Open Dataset (CC0). "
            "Roster snapshot is 2025/26; transfers after the source cutoff are not included."
        )

with quality:
    st.subheader("Coverage and freshness")
    grid = pd.MultiIndex.from_product([LEAGUES, expected], names=["league", "season"]).to_frame(index=False)
    status_rows = completed_coverage.assign(status="✓ Complete")
    live_status = coverage[coverage.season == live_season].assign(status="● Live partial")
    status_rows = pd.concat([status_rows, live_status], ignore_index=True)
    grid = grid.merge(status_rows, how="left").fillna({"status": "Missing"})
    grid["league"] = grid.league.map(LEAGUES)
    grid["season"] = grid.season.map(season_label)
    expected_completed = len(LEAGUES) * len(completed_seasons)
    live_leagues = coverage[coverage.season == live_season].league.nunique()
    impossible_shots = int((
        (fixtures.home_sot > fixtures.home_shots)
        | (fixtures.away_sot > fixtures.away_shots)
    ).fillna(False).sum())
    q1, q2, q3, q4, q5 = st.columns(5)
    q1.metric("Completed coverage", f"{len(completed_coverage)}/{expected_completed}")
    q2.metric("Live competitions", f"{live_leagues}/{len(RECENT_LEAGUES)}")
    q3.metric("Match records", f"{len(fixtures):,}")
    q4.metric("Reference rows", f"{len(reference_standings):,}")
    q5.metric("Impossible shot rows", impossible_shots)
    freshness_notes = []
    if not reference_standings.empty:
        reference_refresh = pd.to_datetime(reference_standings.fetched_at).max()
        freshness_notes.append(f"Reference standings refreshed {reference_refresh:%d %b %Y %H:%M}")
    if not analytics_metadata.empty:
        analytics_refresh = pd.to_datetime(analytics_metadata.refreshed_at).max()
        freshness_notes.append(f"Analytics cache refreshed {analytics_refresh:%d %b %Y %H:%M}")
    if freshness_notes:
        st.caption(" · ".join(freshness_notes))
    st.dataframe(grid.pivot(index="league", columns="season", values="status"), width="stretch")
    st.markdown("#### Current-season and player-source coverage")
    e1, e2, e3, e4, e5 = st.columns(5)
    e1.metric("Recent competitions", recent_matches.league.nunique() if not recent_matches.empty else 0)
    e2.metric("Completed results", f"{len(recent_matches):,}")
    e3.metric("Tracked players", f"{len(open_players):,}", f"{open_players.team.nunique() if not open_players.empty else 0}/12 clubs")
    e4.metric("Player stat rows", f"{len(open_player_stats):,}", "Five seasons")
    e5.metric("Artwork", f"{len(team_media) + len(competition_media):,}", "Cached locally")
    extended_refreshes = []
    for dataset in (recent_matches, recent_events, open_players, open_player_stats):
        if not dataset.empty and "fetched_at" in dataset:
            extended_refreshes.append(pd.to_datetime(dataset.fetched_at).max())
    if extended_refreshes:
        st.caption(f"Extended free-source data refreshed {max(extended_refreshes):%d %b %Y %H:%M}")
    with st.expander("Ingestion history"):
        st.dataframe(runs.drop(columns=["run_id"]), hide_index=True, width="stretch")
    st.markdown("#### Shot-field coverage")
    quality_shots = shot_coverage_frame.copy()
    quality_shots["Competition"] = quality_shots.league.map(RECENT_LEAGUES)
    quality_shots["Season"] = quality_shots.season.map(season_label)
    st.dataframe(
        quality_shots[["Competition", "Season", "matches", "shot_matches", "coverage_pct"]],
        hide_index=True, width="stretch",
        column_config={"coverage_pct": st.column_config.ProgressColumn("Coverage", min_value=0, max_value=100, format="%.1f%%")},
    )
    st.info(
        "The player explorer uses the CC0 Transfermarkt Open Dataset for the 2025/26 featured-club snapshot and published appearance totals. "
        "Its upstream updates paused in July 2026, so it does not claim current 2026/27 squads. TheSportsDB remains an artwork and profile-image fallback."
    )

if len(completed_coverage) < len(LEAGUES) * len(completed_seasons):
    st.warning(
        f"Completed-season coverage: {len(completed_coverage)}/{len(LEAGUES) * len(completed_seasons)} league-seasons. "
        "Missing partitions are excluded."
    )
st.divider()
st.caption("Data: Football-Data.co.uk public CSV archive · Transfermarkt Open Dataset (CC0) · TheSportsDB media · Match-derived analytics · Cached locally")
