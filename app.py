import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from football_analysis.config import CLUBS, DB, LEAGUES, label, seasons


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
            return (
                con.sql("SELECT * FROM team_seasons").df(),
                con.sql("SELECT * FROM team_matches").df(),
                con.sql("SELECT * FROM ingestion_runs ORDER BY fetched_at DESC").df(),
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
    .hero {padding: 25px 28px; border-radius: 22px; background: linear-gradient(110deg, rgba(41,77,115,.85), rgba(26,119,105,.55)); border: 1px solid rgba(114,231,199,.22); margin-bottom: 20px;}
    .hero h1 {margin: 0; font-size: 2.25rem; letter-spacing: -.04em;}
    .hero p {margin: 8px 0 0; color: #c7d7e8;}
    .eyebrow {color: #70edc9; text-transform: uppercase; letter-spacing: .13em; font-weight: 700; font-size: .75rem;}
    .section-note {color: #9fb2c8; font-size: .9rem; margin-top: -10px; margin-bottom: 10px;}
    .form-row {display:flex; gap:7px; flex-wrap:wrap; margin: 8px 0 20px;}
    .form-pill {width:31px; height:31px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-weight:800; color:white;}
    .win {background:#1ca77b}.draw {background:#68788e}.loss {background:#dc5362}
    div[data-baseweb="tab-list"] {gap: 8px;}
    div[data-baseweb="tab"] {background: rgba(24,39,60,.65); border-radius: 10px; padding: 9px 16px;}
    div[data-baseweb="tab"][aria-selected="true"] {background: rgba(66,190,157,.18);}
    .stDataFrame {border: 1px solid rgba(255,255,255,.07); border-radius: 12px; overflow: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

data = load_data()
if data is None:
    st.info("The dashboard database is not available yet. Run the ingestion command from the README, then refresh this page.")
    st.stop()

summaries, games, runs = data
expected = seasons()
summaries = summaries[summaries.season.isin(expected)].copy()
games = games[games.season.isin(expected)].copy()
coverage = summaries[["league", "season"]].drop_duplicates()
if summaries.empty:
    st.info("No complete seasons are loaded yet. Run ingestion, then return to this page.")
    st.stop()

elite_available = [team for team in CLUBS if team in set(summaries.team)]

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
    league_filter = st.multiselect(
        "Competitions", options=list(LEAGUES), default=list(LEAGUES),
        format_func=lambda code: LEAGUES[code], placeholder="Select competitions",
    )
    available_clubs = [
        team for team in elite_available
        if not summaries[
            (summaries.team == team) & summaries.league.isin(league_filter)
            & summaries.season.isin(year_filter)
        ].empty
    ]
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
        selected_club = available_clubs[0] if available_clubs else None
        compare_clubs = available_clubs
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

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">European club performance lab</div>
      <h1>Football Intelligence</h1>
      <p>Compare elite clubs, inspect league tables, and follow match-by-match form across five seasons.</p>
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
st.caption(f"Results through {latest_date:%d %B %Y}. Each selected club's performance is counted independently.")

overview, standings_tab, club_lab, matches_tab, quality = st.tabs(
    ["Overview", "League tables", "Club lab", "Match explorer", "Data quality"]
)

with overview:
    if analysis_mode == "Competition view":
        overview_rows = summaries[
            summaries.league.isin(league_filter) & summaries.season.isin(year_filter)
        ].copy()
        overview_rows["Club"] = overview_rows.team
    else:
        overview_rows = selected.copy()
        overview_rows["Club"] = overview_rows.team.map(CLUBS)
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
    table = summaries[(summaries.league == table_league) & (summaries.season == table_year)].copy()
    table = table.sort_values(["points", "goal_difference", "goals_for"], ascending=False).reset_index(drop=True)
    table.insert(0, "Rank", range(1, len(table) + 1))
    table["Club"] = table.team.map(CLUBS).fillna(table.team)
    table["Form"] = table.team.map(
        lambda team: " ".join(
            games[
                (games.league == table_league) & (games.season == table_year)
                & (games.team == team)
            ].sort_values("match_date").tail(form_window).points.map(result_letter)
        )
    )
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
    st.caption("Administrative deductions and competition-specific official tiebreakers are excluded.")

with club_lab:
    focus_club = st.selectbox(
        "Club", available_clubs,
        index=available_clubs.index(selected_club) if selected_club in available_clubs else 0,
        format_func=lambda team: CLUBS[team], key="lab_club",
    )
    club_games = games[
        (games.team == focus_club) & games.season.isin(year_filter)
    ].sort_values("match_date").copy()
    recent = club_games.tail(form_window)
    form_html = "".join(
        f'<span class="form-pill {"win" if p == 3 else "draw" if p == 1 else "loss"}">{result_letter(p)}</span>'
        for p in recent.points
    )
    st.markdown(
        f"### {CLUBS[focus_club]} <span style='color:#8fa6bd;font-size:1rem'>recent form</span>",
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="form-row">{form_html}</div>', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns(4)
    f1.metric(f"Last {len(recent)} PPG", f"{recent.points.mean():.2f}")
    f2.metric("Win rate", f"{100*(club_games.points == 3).mean():.1f}%")
    f3.metric("Goal difference", f"{int((club_games.gf-club_games.ga).sum()):+d}")
    f4.metric("Clean-sheet rate", f"{100*(club_games.ga == 0).mean():.1f}%")

    club_games["Rolling PPG"] = club_games.points.rolling(form_window, min_periods=1).mean()
    form_chart = px.line(
        club_games, x="match_date", y="Rolling PPG", color="season",
        title=f"Rolling {form_window}-match form", labels={"match_date": "Match date"},
    )
    form_chart.add_hline(
        y=2, line_dash="dot", line_color="rgba(255,255,255,.35)", annotation_text="2.0 PPG",
    )
    st.plotly_chart(style_chart(form_chart), width="stretch")

    radar_metrics = ["goals_per_game", "points_per_game", "win_rate", "clean_sheets"]
    benchmark = summaries[summaries.season.isin(year_filter)].groupby("team", as_index=False)[radar_metrics].mean()
    focus_index = benchmark.index[benchmark.team == focus_club][0]
    values = [float(benchmark[metric].rank(pct=True).loc[focus_index] * 100) for metric in radar_metrics]
    radar = go.Figure(go.Scatterpolar(
        r=values + values[:1],
        theta=["Scoring", "Points", "Win rate", "Clean sheets", "Scoring"],
        fill="toself", line_color=ACCENT, fillcolor="rgba(87,230,187,.25)",
    ))
    radar.update_layout(
        title="Five-season percentile profile", showlegend=False,
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 100], gridcolor="rgba(255,255,255,.12)"),
            angularaxis=dict(gridcolor="rgba(255,255,255,.12)"),
        ),
    )
    st.plotly_chart(style_chart(radar), width="stretch")

with matches_tab:
    st.subheader("Match explorer")
    e1, e2, e3 = st.columns([1.2, 1, 1])
    match_club = e1.selectbox(
        "Club", available_clubs, format_func=lambda team: CLUBS[team], key="match_club",
    )
    opponent_options = sorted(games.loc[
        (games.team == match_club) & games.season.isin(year_filter), "opponent"
    ].unique())
    opponent = e2.selectbox("Opponent", ["All opponents"] + opponent_options)
    venue = e3.segmented_control("Venue", ["All", "Home", "Away"], default="All")
    rows = games[(games.team == match_club) & games.season.isin(year_filter)].copy()
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

with quality:
    st.subheader("Coverage and freshness")
    grid = pd.MultiIndex.from_product([LEAGUES, expected], names=["league", "season"]).to_frame(index=False)
    grid = grid.merge(coverage.assign(status="✓ Complete"), how="left").fillna({"status": "Missing"})
    grid["league"] = grid.league.map(LEAGUES)
    grid["season"] = grid.season.map(label)
    q1, q2, q3 = st.columns(3)
    q1.metric("League-seasons", f"{len(coverage)}/25")
    q2.metric("Match records", f"{len(games)//2:,}")
    q3.metric("Successful loads", int((runs.status == "success").sum()))
    st.dataframe(grid.pivot(index="league", columns="season", values="status"), width="stretch")
    with st.expander("Ingestion history"):
        st.dataframe(runs.drop(columns=["run_id"]), hide_index=True, width="stretch")
    st.info("Player goals, assists, age, minutes, possession and xG are unavailable in the current source and are never inferred.")

if len(coverage) < 25:
    st.warning(f"Coverage: {len(coverage)}/25 complete league-seasons. Missing partitions are excluded.")
st.divider()
st.caption("Data: Football-Data.co.uk public historical CSV archive · Match-derived analytics · Cached locally")
