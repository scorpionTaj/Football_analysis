"""Populate team_media in DuckDB for all clubs and national teams across all competitions."""

import concurrent.futures
import json
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
import duckdb

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "football.duckdb"

# Well-known national team badges for World Cup
WORLD_CUP_TEAMS = {
    "Argentina": "https://r2.thesportsdb.com/images/media/team/badge/7a3y0t1534960309.png",
    "France": "https://r2.thesportsdb.com/images/media/team/badge/d9l6r11534960341.png",
    "Brazil": "https://r2.thesportsdb.com/images/media/team/badge/1n4x891534960317.png",
    "England": "https://r2.thesportsdb.com/images/media/team/badge/4vfqk01534960334.png",
    "Spain": "https://r2.thesportsdb.com/images/media/team/badge/78x8f41534960370.png",
    "Germany": "https://r2.thesportsdb.com/images/media/team/badge/8m1z981534960347.png",
    "Portugal": "https://r2.thesportsdb.com/images/media/team/badge/i0m6v21534960363.png",
    "Netherlands": "https://r2.thesportsdb.com/images/media/team/badge/97a5a81534960359.png",
    "Italy": "https://r2.thesportsdb.com/images/media/team/badge/25m67d1534960353.png",
    "Croatia": "https://r2.thesportsdb.com/images/media/team/badge/4l9h181534960328.png",
    "Morocco": "https://r2.thesportsdb.com/images/media/team/badge/70w2211534960357.png",
    "Japan": "https://r2.thesportsdb.com/images/media/team/badge/0o2f7t1534960355.png",
    "USA": "https://r2.thesportsdb.com/images/media/team/badge/6t29a81534960378.png",
    "United States": "https://r2.thesportsdb.com/images/media/team/badge/6t29a81534960378.png",
    "Mexico": "https://r2.thesportsdb.com/images/media/team/badge/r1d8m91534960356.png",
    "Belgium": "https://r2.thesportsdb.com/images/media/team/badge/5u5y541534960315.png",
    "Uruguay": "https://r2.thesportsdb.com/images/media/team/badge/w75x1k1534960377.png",
    "Switzerland": "https://r2.thesportsdb.com/images/media/team/badge/9d5a9d1534960372.png",
    "Senegal": "https://r2.thesportsdb.com/images/media/team/badge/95k7j31534960368.png",
    "Colombia": "https://r2.thesportsdb.com/images/media/team/badge/e494o61534960326.png",
    "Poland": "https://r2.thesportsdb.com/images/media/team/badge/729x7b1534960362.png",
    "Denmark": "https://r2.thesportsdb.com/images/media/team/badge/v6o7l51534960331.png",
    "Australia": "https://r2.thesportsdb.com/images/media/team/badge/27o1d01534960310.png",
    "Korea Republic": "https://r2.thesportsdb.com/images/media/team/badge/j7v8p51534960371.png",
    "South Korea": "https://r2.thesportsdb.com/images/media/team/badge/j7v8p51534960371.png",
    "Saudi Arabia": "https://r2.thesportsdb.com/images/media/team/badge/3w5r271534960367.png",
    "Ghana": "https://r2.thesportsdb.com/images/media/team/badge/27u9q51534960348.png",
    "Cameroon": "https://r2.thesportsdb.com/images/media/team/badge/h0g5u31534960323.png",
    "Canada": "https://r2.thesportsdb.com/images/media/team/badge/2k212j1534960324.png",
    "Ecuador": "https://r2.thesportsdb.com/images/media/team/badge/2836261534960333.png",
    "Qatar": "https://r2.thesportsdb.com/images/media/team/badge/s5u8b11534960365.png",
    "Tunisia": "https://r2.thesportsdb.com/images/media/team/badge/8m22l31534960374.png",
    "Iran": "https://r2.thesportsdb.com/images/media/team/badge/m06j611534960351.png",
    "Serbia": "https://r2.thesportsdb.com/images/media/team/badge/q2s6e81534960369.png",
    "Wales": "https://r2.thesportsdb.com/images/media/team/badge/341d3x1534960379.png",
    "Costa Rica": "https://r2.thesportsdb.com/images/media/team/badge/03f0b21534960327.png",
    "Egypt": "https://r2.thesportsdb.com/images/media/team/badge/8n41m01534960335.png",
    "Nigeria": "https://r2.thesportsdb.com/images/media/team/badge/8b07s91534960360.png",
    "Algeria": "https://r2.thesportsdb.com/images/media/team/badge/02p8z01534960308.png",
    "Chile": "https://r2.thesportsdb.com/images/media/team/badge/m49y3v1534960325.png",
    "Peru": "https://r2.thesportsdb.com/images/media/team/badge/9d54g81534960361.png",
    "Ukraine": "https://r2.thesportsdb.com/images/media/team/badge/9970e71534960375.png",
    "Sweden": "https://r2.thesportsdb.com/images/media/team/badge/7f18b51534960373.png",
    "Czech Republic": "https://r2.thesportsdb.com/images/media/team/badge/y12o841534960330.png",
    "Austria": "https://r2.thesportsdb.com/images/media/team/badge/256l421534960311.png",
    "Turkey": "https://r2.thesportsdb.com/images/media/team/badge/8r4v121534960376.png",
    "Scotland": "https://r2.thesportsdb.com/images/media/team/badge/7854m91534960366.png",
    "Norway": "https://r2.thesportsdb.com/images/media/team/badge/b7y4891534960358.png",
}

CLEAN_QUERY = {
    "Man City": "Manchester City",
    "Man United": "Manchester United",
    "Nott'm Forest": "Nottingham Forest",
    "Wolves": "Wolverhampton",
    "Ath Madrid": "Atletico Madrid",
    "Ath Bilbao": "Athletic Bilbao",
    "Ein Frankfurt": "Eintracht Frankfurt",
    "M'gladbach": "Borussia Monchengladbach",
    "FC Koln": "1. FC Koln",
    "St Pauli": "FC St. Pauli",
    "Paris SG": "Paris Saint-Germain",
    "Inter": "Inter Milan",
    "Milan": "AC Milan",
    "Vallecano": "Rayo Vallecano",
    "Celta": "Celta Vigo",
    "Sociedad": "Real Sociedad",
    "Betis": "Real Betis",
    "Sporting CP": "Sporting Lisbon",
    "Leverkusen": "Bayer Leverkusen",
    "Dortmund": "Borussia Dortmund",
    "Hertha": "Hertha BSC",
    "Greuther Furth": "Greuther Furth",
}

def search_team(team_name: str):
    query = CLEAN_QUERY.get(team_name, team_name)
    url = "https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            teams = data.get("teams") or []
            if teams:
                t = teams[0]
                badge = t.get("strBadge") or ""
                logo = t.get("strLogo") or ""
                tid = str(t.get("idTeam", ""))
                return team_name, tid, badge, logo
    except Exception:
        pass
    return team_name, None, None, None

def main():
    con = duckdb.connect(str(DB_PATH))
    now = datetime.now()

    # Ingest national teams
    for nation, badge in WORLD_CUP_TEAMS.items():
        con.execute(
            """
            INSERT INTO team_media (source, team_id, team, badge_url, logo_url, banner_url, fanart_url, stadium_url, fetched_at)
            VALUES ('thesportsdb', ?, ?, ?, ?, '', '', '', ?)
            ON CONFLICT (source, team) DO UPDATE SET badge_url = EXCLUDED.badge_url, logo_url = EXCLUDED.logo_url
            """,
            [nation.lower().replace(" ", ""), nation, badge, badge, now],
        )

    # Get all teams currently in matches
    all_teams = set()
    for t in ['matches', 'recent_matches']:
        all_teams.update(con.execute(f'SELECT DISTINCT home_team FROM {t}').df()['home_team'].tolist())
        all_teams.update(con.execute(f'SELECT DISTINCT away_team FROM {t}').df()['away_team'].tolist())
    all_teams.update(con.execute('SELECT DISTINCT home_team FROM tournament_matches').df()['home_team'].tolist())
    all_teams.update(con.execute('SELECT DISTINCT away_team FROM tournament_matches').df()['away_team'].tolist())

    print(f"Total unique match teams to resolve: {len(all_teams)}")

    # Exclude teams that already have badge in team_media
    existing = set(con.execute("SELECT team FROM team_media WHERE badge_url IS NOT NULL AND badge_url != ''").df()['team'].tolist())
    to_fetch = [t for t in all_teams if t not in existing]
    print(f"Teams needing badge search: {len(to_fetch)}")

    success_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(search_team, t): t for t in to_fetch}
        for future in concurrent.futures.as_completed(futures):
            t_name, tid, badge, logo = future.result()
            if badge:
                con.execute(
                    """
                    INSERT INTO team_media (source, team_id, team, badge_url, logo_url, banner_url, fanart_url, stadium_url, fetched_at)
                    VALUES ('thesportsdb', ?, ?, ?, ?, '', '', '', ?)
                    ON CONFLICT (source, team) DO UPDATE SET badge_url = EXCLUDED.badge_url, logo_url = EXCLUDED.logo_url
                    """,
                    [tid or "", t_name, badge, logo or "", now],
                )
                success_count += 1
                print(f"Saved badge for {t_name} -> {badge[:50]}...")

    print(f"Successfully added {success_count} badges!")
    total = con.execute("SELECT count(*) FROM team_media WHERE badge_url IS NOT NULL AND badge_url != ''").fetchone()[0]
    print(f"Total teams with badges in DuckDB: {total}")
    con.close()

if __name__ == "__main__":
    main()
