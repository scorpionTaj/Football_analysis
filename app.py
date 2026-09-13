import html

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from football_analysis.config import CLUBS, DB, LEAGUES, RECENT_LEAGUES, label, seasons
from football_analysis.analytics import elo_history, shot_coverage, team_shot_efficiency
from football_analysis.teams import display_team, team_key


ACCENT = "#57e6bb"
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#dce7f5"), margin=dict(l=20, r=20, t=55, b=20),
    hoverlabel=dict(bgcolor="#142238", font_color="#ffffff"),
)


def style_chart(fig, height=430):
    fig.update_layout(**PLOT_LAYOUT, height=height, legend_title_text="")
    fig.update_xaxes(gridcolor="rgba(255,255,255,.07)", zeroline=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,.07)", zeroline=False)
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
    [data-testid="stAppViewContainer"] {background: radial-gradient(circle at 78% 0%, #14243a 0, #0a111d 35%, #080e18 72%);}
    [data-testid="stSidebar"] {background: linear-gradient(180deg, #132238, #0d1727); border-right: 1px solid rgba(255,255,255,.07);}
    [data-testid="stMetric"] {background: linear-gradient(145deg, rgba(30,49,74,.92), rgba(16,28,45,.92)); border: 1px solid rgba(255,255,255,.08); padding: 18px; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,.16);}
    [data-testid="stMetricValue"] {color: #f6fbff;}
    [data-testid="stMetricDelta"] {font-size: .8rem;}
    .hero {position:relative; overflow:hidden; padding: 25px 28px; border-radius: 22px; background: linear-gradient(110deg, rgba(41,77,115,.9), rgba(26,119,105,.62)); border: 1px solid rgba(114,231,199,.22); margin-bottom: 20px; box-shadow:0 24px 60px rgba(0,0,0,.22);}
    .hero::after {content:""; position:absolute; width:270px; height:270px; right:-90px; top:-150px; border-radius:50%; background:radial-gradient(circle, rgba(112,237,201,.25), transparent 68%);}
    .hero-layout {display:flex; align-items:center; justify-content:space-between; gap:24px;}
    .hero-copy {position:relative; z-index:2;}
    .hero h1 {margin: 0; font-size: 2.25rem; letter-spacing: -.04em;}
    .hero p {margin: 8px 0 0; color: #c7d7e8;}
    .hero-mark {position:relative; z-index:2; flex:0 0 112px; width:112px; height:112px; display:grid; place-items:center; border-radius:26px; background:rgba(7,15,27,.35); border:1px solid rgba(255,255,255,.14); box-shadow:inset 0 1px rgba(255,255,255,.08), 0 18px 45px rgba(0,0,0,.22); animation:mark-in .65s cubic-bezier(.2,.8,.2,1) both;}
    .hero-mark img {width:82px; height:82px; object-fit:contain; filter:drop-shadow(0 10px 18px rgba(0,0,0,.32));}
    .eyebrow {color: #70edc9; text-transform: uppercase; letter-spacing: .13em; font-weight: 700; font-size: .75rem;}
    .section-note {color: #9fb2c8; font-size: .9rem; margin-top: -10px; margin-bottom: 10px;}
    .form-row {display:flex; gap:7px; flex-wrap:wrap; margin: 8px 0 20px;}
    .form-pill {width:31px; height:31px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-weight:800; color:white;}
    .win {background:#1ca77b}.draw {background:#68788e}.loss {background:#dc5362}
    div[data-baseweb="tab-list"] {gap: 8px;}
    div[data-baseweb="tab"] {background: rgba(24,39,60,.65); border-radius: 10px; padding: 9px 16px;}
    div[data-baseweb="tab"][aria-selected="true"] {background: rgba(66,190,157,.18);}
    .stDataFrame {border: 1px solid rgba(255,255,255,.07); border-radius: 12px; overflow: hidden;}
    .identity-card {display:flex; align-items:center; gap:18px; padding:18px 20px; margin:4px 0 18px; border-radius:18px; background:linear-gradient(120deg,rgba(27,44,68,.9),rgba(17,37,48,.78)); border:1px solid rgba(112,237,201,.16); animation:card-in .55s ease-out both;}
    .identity-card img {width:76px; height:76px; object-fit:contain; filter:drop-shadow(0 10px 16px rgba(0,0,0,.32)); transition:transform .3s ease;}
    .identity-card:hover img {transform:scale(1.08) rotate(-2deg);}
    .identity-card h2 {margin:2px 0 3px; font-size:1.65rem;}
    .identity-card p {margin:0; color:#9fb2c8;}
    .art-kicker {color:#70edc9; font-size:.73rem; font-weight:800; text-transform:uppercase; letter-spacing:.12em;}
    .badge-rail {display:flex; gap:10px; flex-wrap:wrap; margin:10px 0 18px;}
    .badge-chip {display:flex; align-items:center; gap:8px; padding:8px 11px; border-radius:999px; background:rgba(24,39,60,.72); border:1px solid rgba(255,255,255,.08); color:#dce7f5; font-size:.82rem; animation:card-in .4s ease-out both;}
    .badge-chip img {width:25px; height:25px; object-fit:contain;}
    .player-stage {position:relative; min-height:300px; display:flex; align-items:flex-end; justify-content:center; overflow:hidden; border-radius:24px; background:radial-gradient(circle at 50% 42%,rgba(87,230,187,.25),transparent 42%),linear-gradient(165deg,#213753,#101a2a); border:1px solid rgba(112,237,201,.18); box-shadow:0 22px 55px rgba(0,0,0,.25); animation:card-in .55s ease-out both;}
    .player-stage::before {content:""; position:absolute; width:190px; height:190px; top:38px; border:1px solid rgba(112,237,201,.3); border-radius:50%; animation:ring-pulse 3.4s ease-in-out infinite;}
    .player-stage img {position:relative; z-index:2; width:94%; max-height:310px; object-fit:contain; object-position:center bottom; filter:drop-shadow(0 18px 22px rgba(0,0,0,.42)); animation:player-float 5s ease-in-out infinite;}
    .player-number {position:absolute; z-index:1; right:15px; top:7px; font-size:5.6rem; line-height:1; font-weight:900; color:rgba(255,255,255,.07); letter-spacing:-.08em;}
    .no-art {width:82px; height:82px; display:grid; place-items:center; border-radius:50%; background:linear-gradient(145deg,#2b496b,#1aa37d); color:white; font-size:1.6rem; font-weight:900;}
    @keyframes card-in {from{opacity:0; transform:translateY(12px)} to{opacity:1; transform:translateY(0)}}
    @keyframes mark-in {from{opacity:0; transform:scale(.8) rotate(-6deg)} to{opacity:1; transform:scale(1) rotate(0)}}
    @keyframes player-float {0%,100%{transform:translateY(0)} 50%{transform:translateY(-7px)}}
    @keyframes ring-pulse {0%,100%{transform:scale(.92);opacity:.42} 50%{transform:scale(1.08);opacity:.8}}
    @media (prefers-reduced-motion: reduce) {.hero-mark,.identity-card,.badge-chip,.player-stage,.player-stage img,.player-stage::before{animation:none!important;transition:none!important}}
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
expected = seasons()
summaries = summaries[summaries.season.isin(expected)].copy()
games = games[games.season.isin(expected)].copy()
fixtures = fixtures[fixtures.season.isin(expected)].copy()
reference_standings = reference_standings[
    reference_standings.season.isin(expected)
].copy() if not reference_standings.empty else reference_standings
coverage = summaries[["league", "season"]].drop_duplicates()
if summaries.empty:
    st.info("No complete seasons are loaded yet. Run ingestion, then return to this page.")
    st.stop()

elite_available = [team for team in CLUBS if team in set(summaries.team)]


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
    st.caption("Build your analysis")
    analysis_mode = st.radio(
        "Analysis mode", ["Compare clubs", "Club focus", "Competition view"],
        captions=["Benchmark elite teams", "One club in depth", "Full league standings"],
    )
    st.divider()
    year_range = st.select_slider(
        "Season range", options=expected, value=(expected[0], expected[-1]),
        format_func=label, help="Choose the first and last completed season.",
    )
    year_filter = list(range(year_range[0], year_range[1] + 1))
    if analysis_mode == "Competition view":
        competition_focus = st.selectbox(
            "Competition", options=list(LEAGUES),
            format_func=lambda code: LEAGUES[code],
        )
        league_filter = [competition_focus]
        chart_limit = st.selectbox(
            "Overview clubs", options=[5, 10, "All"], index=1,
            format_func=lambda value: "All clubs" if value == "All" else f"Top {value}",
            help="League tables remain complete; this limit keeps charts readable.",
        )
    else:
        league_filter = st.multiselect(
            "Competitions", options=list(LEAGUES), default=list(LEAGUES),
            format_func=lambda code: LEAGUES[code], placeholder="Select competitions",
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
    st.caption("Domestic leagues · Free public data · Five completed seasons")

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
    hero_text = "Follow form, strength, scoring and every league result across five completed seasons."
    hero_image = team_badge(selected_club)
elif analysis_mode == "Competition view":
    hero_title = LEAGUES[league_filter[0]]
    hero_eyebrow = "Competition intelligence"
    hero_text = "Explore the complete table, season trends and every club in the selected domestic league."
    hero_image = competition_badge(league_filter[0])
else:
    hero_title = "Football Intelligence"
    hero_eyebrow = "European club performance lab"
    hero_text = "Compare elite clubs, inspect league tables, and follow match-by-match form across five seasons."
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
m5.metric("Peak season", f"{best_row.points_per_game:.2f}", f"{best_row.team} · {label(best_row.season)}")
if analysis_mode == "Competition view":
    st.caption(f"Results through {latest_date:%d %B %Y}. Competition totals include every club in the selected league.")
else:
    st.caption(f"Results through {latest_date:%d %B %Y}. Each selected club's performance is counted independently.")

overview, standings_tab, club_lab, shots_tab, matches_tab, recent_tab, players_tab, quality = st.tabs(
    [
        "Overview", "League tables", "Club lab", "Shot lab", "Match explorer",
        "Recent matches", "Players", "Data quality",
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
            f"Charts show {len(compare_clubs)} clubs from the {label(latest_competition_year)} table. "
            "The League tables tab still shows every club."
        )
    else:
        overview_rows = selected.copy()
        overview_rows["Club"] = overview_rows.team.map(display_team)
    overview_rows["Season"] = overview_rows.season.map(label)
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
    elo_rows["Season"] = elo_rows.season.map(label)
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
        "Competition", league_filter, format_func=lambda code: LEAGUES[code], key="table_league",
    )
    valid_years = [
        year for year in sorted(summaries.loc[summaries.league == table_league, "season"].unique(), reverse=True)
        if year in year_filter
    ]
    table_year = c2.selectbox("Season", valid_years, format_func=label, key="table_year")
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
    st.caption("Results-derived points exclude administrative deductions and official competition-specific tiebreakers.")
    st.markdown("#### External reference table")
    reference = reference_standings[
        (reference_standings.league == table_league)
        & (reference_standings.season == table_year)
    ].sort_values("rank") if not reference_standings.empty else pd.DataFrame()
    if reference.empty:
        st.info("No external reference table is cached for this competition and season.")
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
        f'<p>{html.escape(" · ".join(LEAGUES[code] for code in focus_leagues))}</p></div></div>',
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
    coverage_rows["Competition"] = coverage_rows.league.map(LEAGUES)
    coverage_rows["Season"] = coverage_rows.season.map(label)
    gated = shot_efficiency[
        shot_efficiency.league.isin(league_filter)
        & shot_efficiency.season.isin(year_filter)
        & shot_efficiency.team.isin(compare_clubs if compare_clubs else elite_available)
    ].copy()
    if gated.empty:
        st.info("No selected club-season passes the 95% shot-data coverage gate.")
    else:
        gated["Club"] = gated.team.map(CLUBS).fillna(gated.team)
        gated["Season"] = gated.season.map(label)
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
        display["season"] = display.season.map(label)
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

with recent_tab:
    st.subheader("Current-season match centre")
    st.markdown(
        '<div class="section-note">Completed matches come from the twice-weekly public CSV feed; the newest result and next event per league are supplemented by TheSportsDB.</div>',
        unsafe_allow_html=True,
    )
    if recent_matches.empty and recent_events.empty:
        st.info("Current-season data has not been synchronized yet. Run football-sync-recent, then refresh.")
    else:
        recent_options = [
            code for code in RECENT_LEAGUES
            if code in set(recent_matches.get("league", pd.Series(dtype=str)))
            or code in set(recent_events.get("league", pd.Series(dtype=str)))
        ]
        recent_filter = st.multiselect(
            "Recent competitions", recent_options, default=recent_options,
            format_func=lambda code: RECENT_LEAGUES[code],
        )
        st.markdown(badge_rail(recent_filter), unsafe_allow_html=True)
        history = recent_matches[
            recent_matches.league.isin(recent_filter)
        ][[
            "league", "season", "match_date", "home_team", "away_team",
            "home_goals", "away_goals", "source", "fetched_at",
        ]].copy() if not recent_matches.empty else pd.DataFrame()
        event_history = recent_events[
            recent_events.league.isin(recent_filter)
            & (recent_events.event_kind == "past")
            & recent_events.home_goals.notna()
            & recent_events.away_goals.notna()
        ][[
            "league", "season", "match_date", "home_team", "away_team",
            "home_goals", "away_goals", "source", "fetched_at",
        ]].copy() if not recent_events.empty else pd.DataFrame()
        combined = pd.concat([history, event_history], ignore_index=True)
        if combined.empty:
            st.info("No completed current-season matches fit these competitions.")
        else:
            combined["home_key"] = combined.home_team.map(team_key)
            combined["away_key"] = combined.away_team.map(team_key)
            combined = combined.sort_values(["match_date", "fetched_at"]).drop_duplicates(
                ["league", "match_date", "home_key", "away_key"], keep="last"
            )
            combined["Competition"] = combined.league.map(RECENT_LEAGUES)
            combined["Home"] = combined.home_team.map(display_team)
            combined["Away"] = combined.away_team.map(display_team)
            combined["Score"] = (
                combined.home_goals.astype(int).astype(str)
                + "–" + combined.away_goals.astype(int).astype(str)
            )
            latest_match_date = pd.to_datetime(combined.match_date).max()
            latest_rows = combined.sort_values("match_date", ascending=False)
            rc1, rc2, rc3, rc4 = st.columns(4)
            rc1.metric("Competitions", combined.league.nunique())
            rc2.metric("Current-season matches", len(combined))
            rc3.metric("Latest result", f"{latest_match_date:%d %b %Y}")
            rc4.metric("Goals", int(combined.home_goals.sum() + combined.away_goals.sum()))
            daily = combined.groupby(["match_date", "Competition"], as_index=False).size()
            recent_chart = px.bar(
                daily.sort_values("match_date").tail(80), x="match_date", y="size",
                color="Competition", title="Recent match activity",
                labels={"match_date": "Match date", "size": "Matches"},
            )
            st.plotly_chart(style_chart(recent_chart, 380), width="stretch")
            st.dataframe(
                latest_rows[["match_date", "Competition", "Home", "Score", "Away", "source"]].head(100),
                hide_index=True, width="stretch",
                column_config={
                    "match_date": "Date", "source": "Source",
                },
            )
        upcoming = recent_events[
            recent_events.league.isin(recent_filter)
            & (recent_events.event_kind == "next")
        ].sort_values("match_date").copy() if not recent_events.empty else pd.DataFrame()
        if not upcoming.empty:
            upcoming["Competition"] = upcoming.league.map(RECENT_LEAGUES)
            upcoming["Home"] = upcoming.home_team.map(display_team)
            upcoming["Away"] = upcoming.away_team.map(display_team)
            st.markdown("#### Next listed event per competition")
            st.dataframe(
                upcoming[["match_date", "Competition", "Home", "Away", "status"]],
                hide_index=True, width="stretch",
                column_config={"match_date": "Date", "status": "Status"},
            )
        recent_refreshes = []
        if not recent_matches.empty:
            recent_refreshes.append(pd.to_datetime(recent_matches.fetched_at).max())
        if not recent_events.empty:
            recent_refreshes.append(pd.to_datetime(recent_events.fetched_at).max())
        if recent_refreshes:
            st.caption(f"Last current-season synchronization: {max(recent_refreshes):%d %b %Y %H:%M}")

with players_tab:
    st.subheader("Player explorer")
    st.markdown(
        '<div class="section-note">TheSportsDB free v1 returns up to 10 listed players per team and up to 10 statistic rows per player. Coverage is a transparent sample, not a complete squad register.</div>',
        unsafe_allow_html=True,
    )
    if players.empty:
        st.info("Player profiles have not been synchronized yet. Run football-sync-players, then refresh.")
    else:
        player_clubs = sorted(players.team.dropna().unique(), key=display_team)
        preferred_key = team_key(selected_club) if selected_club else ""
        preferred_club = next(
            (club for club in player_clubs if team_key(club) == preferred_key), player_clubs[0]
        )
        pc1, pc2 = st.columns(2)
        player_club = pc1.selectbox(
            "Player club", player_clubs, index=player_clubs.index(preferred_club),
            format_func=display_team,
        )
        club_players = players[players.team == player_club].sort_values("player")
        player_id = pc2.selectbox(
            "Player", club_players.player_id.tolist(),
            format_func=lambda value: club_players.loc[
                club_players.player_id == value, "player"
            ].iloc[0],
        )
        profile = club_players[club_players.player_id == player_id].iloc[0]
        image_column, profile_column = st.columns([1, 3])
        image_url = _safe_url(profile.cutout_url) or _safe_url(profile.thumb_url)
        with image_column:
            if image_url:
                player_number = html.escape(str(profile.shirt_number or ""))
                st.markdown(
                    f'<div class="player-stage"><span class="player-number">{player_number}</span>'
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
            age = "Unknown" if pd.isna(birth) else str(
                pd.Timestamp.now().year - birth.year
                - ((pd.Timestamp.now().month, pd.Timestamp.now().day) < (birth.month, birth.day))
            )
            pp1, pp2, pp3, pp4 = st.columns(4)
            pp1.metric("Position", profile.position or "Unknown")
            pp2.metric("Nationality", profile.nationality or "Unknown")
            pp3.metric("Age", age)
            pp4.metric("Squad number", profile.shirt_number or "—")
            details = [value for value in [profile.height, profile.weight, profile.status] if value]
            if details:
                st.caption(" · ".join(details))
        stats = player_stats[player_stats.player_id == player_id].copy()
        if stats.empty:
            st.info("The free feed returned no statistic rows for this player.")
        else:
            stats["Competition"] = stats.league
            stats["Season"] = stats.season
            stats_table = stats.pivot_table(
                index=["Competition", "Season"], columns="statistic",
                values="value", aggfunc="first",
            ).reset_index()
            st.markdown("#### Available player statistics")
            st.dataframe(stats_table, hide_index=True, width="stretch")
        st.markdown("#### Sampled club players")
        sampled = club_players[["player", "position", "nationality", "shirt_number"]].rename(
            columns={
                "player": "Player", "position": "Position", "nationality": "Nationality",
                "shirt_number": "Number",
            }
        )
        st.dataframe(sampled, hide_index=True, width="stretch")
        st.caption(
            f"{len(club_players)} player profiles cached for {display_team(player_club)} · "
            f"{len(stats)} statistic rows for the selected player · Source: TheSportsDB"
        )

with quality:
    st.subheader("Coverage and freshness")
    grid = pd.MultiIndex.from_product([LEAGUES, expected], names=["league", "season"]).to_frame(index=False)
    grid = grid.merge(coverage.assign(status="✓ Complete"), how="left").fillna({"status": "Missing"})
    grid["league"] = grid.league.map(LEAGUES)
    grid["season"] = grid.season.map(label)
    expected_partitions = len(LEAGUES) * len(expected)
    loaded_partitions = runs.loc[
        runs.status == "success", ["league", "season"]
    ].drop_duplicates().shape[0]
    impossible_shots = int((
        (fixtures.home_sot > fixtures.home_shots)
        | (fixtures.away_sot > fixtures.away_shots)
    ).fillna(False).sum())
    q1, q2, q3, q4, q5 = st.columns(5)
    q1.metric("League-seasons", f"{len(coverage)}/{expected_partitions}")
    q2.metric("Match records", f"{len(games)//2:,}")
    q3.metric("Loaded partitions", loaded_partitions)
    q4.metric("Reference rows", len(reference_standings), "Top-five only")
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
    e3.metric("Player profiles", f"{len(players):,}", "Capped sample")
    e4.metric("Player stat rows", f"{len(player_stats):,}", "Sparse history")
    e5.metric("Artwork", f"{len(team_media) + len(competition_media):,}", "Cached locally")
    extended_refreshes = []
    for dataset in (recent_matches, recent_events, players, player_stats):
        if not dataset.empty and "fetched_at" in dataset:
            extended_refreshes.append(pd.to_datetime(dataset.fetched_at).max())
    if extended_refreshes:
        st.caption(f"Extended free-source data refreshed {max(extended_refreshes):%d %b %Y %H:%M}")
    with st.expander("Ingestion history"):
        st.dataframe(runs.drop(columns=["run_id"]), hide_index=True, width="stretch")
    st.markdown("#### Shot-field coverage")
    quality_shots = shot_coverage_frame.copy()
    quality_shots["Competition"] = quality_shots.league.map(LEAGUES)
    quality_shots["Season"] = quality_shots.season.map(label)
    st.dataframe(
        quality_shots[["Competition", "Season", "matches", "shot_matches", "coverage_pct"]],
        hide_index=True, width="stretch",
        column_config={"coverage_pct": st.column_config.ProgressColumn("Coverage", min_value=0, max_value=100, format="%.1f%%")},
    )
    st.info(
        "Player profiles and sparse historical goals, assists, appearances and minutes are shown only when TheSportsDB returns them. "
        "The free feed is capped at 10 players per team and 10 statistic rows per player; missing values, possession and xG are never inferred."
    )

if len(coverage) < len(LEAGUES) * len(expected):
    st.warning(f"Coverage: {len(coverage)}/{len(LEAGUES) * len(expected)} complete league-seasons. Missing partitions are excluded.")
st.divider()
st.caption("Data: Football-Data.co.uk public CSV archive · TheSportsDB capped free feed · Match-derived analytics · Cached locally")
