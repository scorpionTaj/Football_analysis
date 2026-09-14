# Player and squad data-source research

Research date: **13 September 2026**

## Decision

Use a hybrid source strategy:

1. **API-Football by API-Sports** should become the primary source for complete current squads and current-season player statistics. Its free plan includes every endpoint and competition, allows 100 requests per day, and exposes a dedicated current-squad endpoint. Twelve squad requests cover the 12 featured clubs, leaving enough daily capacity for team lookup, validation and staged player-stat pages. It requires a free account and API key, and its publication terms require care.
2. **Reep** should be the optional identity layer. Its CC0 snapshots map stable player and club identities across Wikidata, Transfermarkt, FBref, API-Football and many other providers. It should help avoid name-only joins, but it is not a squad or performance-statistics feed.
3. Keep **Football-Data.co.uk** for the project's broad free results history and current match ingestion. Replacing the whole pipeline with a player-oriented API would reduce resilience and waste API quota.
4. Keep **TheSportsDB** only for permitted artwork and supplementary biographies. Its free endpoint returns at most 10 players per team, so it cannot define a complete squad.
5. Use the **Transfermarkt dataset** as a historical enrichment snapshot after labelling its cutoff. Its automated refresh is paused, the data stops on 6 July 2026, and 2026/27 squads are absent.
6. Use **StatsBomb Open Data** only for separately labelled event-analysis demonstrations. Its coverage is deliberately selective and is not a current squad directory.

No free/open source found can reliably provide all of these at once: every current squad member, rich current player statistics, five completed seasons for all 12 clubs, unrestricted image rights, and an open redistribution licence. The design should preserve source provenance at field level rather than presenting a blended record as if it came from one authoritative database.

## Comparison

| Source | Complete current squads for the 12 clubs | Player fields and statistics | Access, quota and refresh | Licence and redistribution | Decision |
|---|---|---|---|---|---|
| **API-Football / API-Sports** | **Best candidate.** `/players/squads?team=ID` returns the current registered squad and all competitions/endpoints are included on the free plan. The 12 target clubs should require 12 squad calls. Actual 2026/27 coverage must be confirmed with the API key and the per-season `coverage` flags before publishing a completeness claim. | Squad records include stable player ID, name, age, number and position; player endpoints add profile/photo and season statistics such as appearances, minutes, goals, assists, cards and other performance groups. Results are paginated at 20 players for the seasonal `/players` query. | Free account and `x-apisports-key`; **100 requests/day**. Free history is limited to recent seasons. Official guidance recommends caching squads daily and checking coverage before making detail calls. Update frequencies are indicative rather than guaranteed. | Proprietary service. Terms prohibit reselling the data, do not grant publication rights, and place responsibility for competition/data rights on the user. Logos/photos require separate rights review. | **Primary current-squad adapter**, with cached ingestion and visible attribution/provenance. Do not make it the only match source. |
| **dcaribou/transfermarkt-datasets** | Previously strong current-club coverage, but **not current enough now**: published data stops on 6 July 2026 and 2026/27 squads are explicitly absent. | 50,000+ player profiles; current club, DOB, nationality, position/sub-position, foot, height, market value, contract, image URL, transfers, appearances, goals, assists, minutes and cards through the cutoff. DuckDB and compressed CSV are ready to query. | No authentication or request quota for downloads. The former weekly pipeline is currently paused with no restart estimate. | The publication is **CC0 1.0**. Treat external image URLs as references; the dataset's CC0 metadata licence does not establish rights in third-party photographs. | **Historical enrichment only** until refresh resumes and a new release covers 2026/27. |
| **Wikidata / WDQS** | Can query active `member of sports team (P54)` statements, but community-maintained membership is uneven. It cannot support a hard complete-squad guarantee for all 12 clubs. | Useful identity and biography fields: QID, names, DOB, nationality, position, height, external provider IDs, club membership qualifiers and sometimes Commons images. It does not provide systematic player-season performance statistics. | No API key. Public SPARQL endpoint has a 60-second query deadline, 60 seconds of processing time per client per 60 seconds, five parallel queries per IP, and a required descriptive User-Agent. Up to six hours of update lag is normal. | Wikidata structured data is **CC0**. Commons images carry their own per-file licences and attribution requirements. | **Biography and identity supplement**, never the sole roster source. |
| **StatsBomb Open Data** | No. It supplies lineups for matches in selected released competitions/seasons, not a current all-club roster index. | Excellent event detail: lineups, passes, shots, pressures, possessions, substitutions and selected 360 frames. Player season/match aggregates can be derived for covered matches. | Public GitHub JSON, no key or quota. New datasets are released selectively rather than on a league-wide current-squad schedule. | Repository terms require naming StatsBomb and using its logo when publishing research, analysis or insights based on the data. | **Event-analysis lab only**; not suitable for the Players catalogue. |
| **football-data.org** | Not on the €0 plan. Team resources can return current squads, but the pricing page puts squads, line-ups and scorers in the **€29/month** “Free + Deep Data” package. | When entitled: player ID, names, DOB, nationality, position, shirt number, market value and contract; match/goal/card detail depends on tier. | Free token: 12 competitions, delayed scores/schedules, fixtures and tables at **10 calls/minute**. Deep player data is paid. | Attribution is required. Terms say API data may not remain referenced after cancellation and that graphics need permission from their owners. | Keep rejected for player ingestion under the no-paid rule. |
| **TheSportsDB v1** | No. The free `lookup_all_players` limit is **10 players per team**, below a full first-team squad. | Good presentation metadata: player ID, name, DOB, nationality, position, height, weight, number, biography, social links and artwork. Free player-stat lookup returns at most 10 rows and coverage is crowd-sourced. | Public v1 key `123`; **30 requests/minute**. V2 and larger response limits are premium. The service is crowd-edited and publishes no completeness SLA. | Terms allow copying/modifying API responses through official endpoints for development projects, require source acknowledgement for paid use, prohibit website scraping, and require a paid subscription for app-store publication. | Keep as **artwork/profile fallback** with visible source and completeness labels. |
| **Sportmonks Football API** | Technically excellent, but its permanent free plan covers only the Danish Superliga and Scottish Premiership. It therefore covers none of the target clubs through free access. | Current and historical squads, profile images, positions, biometrics, appearances, minutes, goals, assists, cards, ratings, passing, duels, shots and more. `/players/latest` exposes records changed in the previous two hours. | API token. Free plan has two fixed leagues; relevant coverage starts at **€29/month for five leagues**. | Commercial proprietary service; a separate contract/terms review would be needed before redistribution. | Strong paid option, **ineligible for this project's free baseline**. |
| **Reep football identity register** | No squad-membership feed. It does not answer who is currently registered for a club. | Roughly 488,000 people and 45,000 teams with stable Reep IDs plus provider-ID bridges for Wikidata, Transfermarkt, FBref, API-Football and 30+ sources; includes core bio fields. | Free dated CSV/DuckDB snapshots. The public register and correction workflow are active; use snapshot metadata to record the exact release ingested. | **CC0 1.0**. | **Recommended optional identity bridge** to prevent ambiguous name matching across providers. |
| **OpenFootball** | No player data in its maintained public match exports. Its schema can model players/rosters, but the published league files are fixtures/results. | Teams, rounds, dates and scores; no dependable player profiles or season statistics. | Public GitHub JSON/TXT, no key. Generated JSON runs daily, while upstream result updates remain community-dependent. | Public domain / **CC0**. | Useful additional open fixture fallback, not a player database. |
| **Creativesdev “Free API Live Football Data” on RapidAPI** | The marketplace exposes player-oriented endpoints, but the plan inspected for this project allows only **100 free requests/month**. That allowance is too small for 12 complete squads plus paginated statistics and refresh validation. | Potentially rich match/player detail, but the marketplace page does not establish five-season completeness or an open-data licence. | RapidAPI subscription/key. Provider-defined quotas can change; the pricing page must be checked while signed in. RapidAPI warns that freemium plans may charge overages and that subscriptions now include bandwidth billing above the included allowance. | Proprietary marketplace feed; no verified open redistribution licence for its football database. | Do not use as the baseline. API-Football's official free plan gives the same 100-request quantity **per day**, with clearer coverage and ingestion documentation. |

## Why API-Football is the practical current-squad baseline

The [official 2026 getting-started guide](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide) identifies `/players/squads` as the current registered squad endpoint, says the free plan includes every endpoint and competition, and recommends daily caching for squad/reference data. The [pricing page](https://www.api-football.com/pricing) currently lists 100 free requests per day and recent-season history. The [official player-ingestion tutorial](https://www.api-football.com/news/post/how-to-get-all-teams-and-players-from-a-league-id) documents 20-player pagination for season statistics and the need to respect rate limits. The [coverage catalogue](https://www.api-football.com/coverage) must still be checked for the specific league and season because player depth varies.

A conservative refresh for this project fits within the free quota:

| Operation | Expected calls |
|---|---:|
| Preflight league/season coverage | 5 |
| Current squads for 12 clubs | 12 |
| Current-season player statistics, normally about two pages per club | about 24–36 |
| Validation/retry reserve | 20 |
| **Expected daily total** | **61–73** |

This estimate is intentionally below the 100-request allowance. The ingestion job should stop before the provider's remaining-quota header reaches a configurable reserve. It should never poll provider endpoints during a frontend page render.

API-Football is free to query but is **not open data**. Its [terms](https://www.api-football.com/terms) prohibit direct resale and say the service does not grant publication rights in the underlying sports data. A portfolio dashboard can use it as an application data source, but any public/commercial launch should re-check the terms and the rights for competition logos and player photos.

## Recommended ingestion design

### Source adapters

- `api_football_squads`: required for the complete current roster when `API_FOOTBALL_KEY` is configured.
- `api_football_player_stats`: optional staged enrichment for the current season, paginated and quota-aware.
- `reep_identity`: optional periodic snapshot import for provider-ID crosswalks.
- `wikidata_bio`: optional low-frequency fill for missing nationality, DOB, height and freely licensed Commons media metadata.
- `thesportsdb_media`: existing artwork/profile fallback; never allowed to truncate or define the primary roster.
- `transfermarkt_snapshot`: historical market-value, transfer and appearance enrichment with an explicit `source_cutoff_date`.

### Tables and provenance

Store provider records without overwriting another source:

```text
players
  internal_player_id, display_name, date_of_birth, nationality,
  primary_position, height_cm, preferred_foot

player_provider_ids
  internal_player_id, provider, provider_player_id, confidence,
  matched_on, source_release, fetched_at

squad_memberships
  internal_player_id, club_id, provider, provider_team_id,
  shirt_number, position, active_from, active_until,
  is_current, source_season, fetched_at

player_season_stats
  internal_player_id, club_id, competition_id, season,
  provider, appearances, starts, minutes, goals, assists,
  yellow_cards, red_cards, rating, fetched_at

media_assets
  entity_type, entity_id, provider, kind, remote_url,
  local_path, licence_url, attribution, fetched_at
```

Keep API-Football's provider IDs as external IDs rather than primary keys. Reconcile players using, in order: a trusted Reep/provider mapping, exact provider ID, or a guarded combination of normalized name + exact DOB + club. Never join players solely by name.

### Completeness checks

Before replacing the active squad snapshot:

1. Confirm the league's current season and player coverage flag.
2. Resolve the exact provider team ID from a checked-in club mapping.
3. Require a successful response for every one of the 12 clubs.
4. Warn on unusual squad sizes, duplicate player IDs, missing names, or multiple active clubs for the same provider player. Preserve the previous good snapshot if validation fails.
5. Record the returned roster count and retrieval time for every club.
6. Mark player statistics as partial until all returned pages are ingested.
7. Display separate badges in the UI for `current squad`, `season statistics`, `historical snapshot`, and `profile enrichment`.

## Source notes and primary references

### API-Football / API-Sports

- [Pricing and free quota](https://www.api-football.com/pricing)
- [2026 API and endpoint guide](https://www.api-football.com/news/post/how-to-get-started-with-api-football-the-complete-beginners-guide)
- [Official pagination tutorial for teams and players](https://www.api-football.com/news/post/how-to-get-all-teams-and-players-from-a-league-id)
- [Competition coverage catalogue](https://www.api-football.com/coverage)
- [Terms of service](https://www.api-football.com/terms)

### Transfermarkt dataset project

- [Official repository and current update warning](https://github.com/dcaribou/transfermarkt-datasets)
- [Player field schema](https://github.com/dcaribou/transfermarkt-datasets/blob/master/transfermarkt_datasets/assets/cur_players.py)
- [Published data package and CC0 declaration](https://github.com/dcaribou/transfermarkt-datasets/blob/master/data/prep/dataset-metadata.json)
- [CC0 licence](https://github.com/dcaribou/transfermarkt-datasets/blob/master/LICENSE)

### Wikidata

- [Official data-access guidance](https://www.wikidata.org/wiki/Wikidata:Reuse)
- [Structured-data licensing](https://www.wikidata.org/wiki/Wikidata:Licensing)
- [Wikidata Query Service limits](https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual#Query_limits)
- [`member of sports team` data model and qualifiers](https://www.wikidata.org/wiki/Property:P54)

### StatsBomb Open Data

- [Official open-data repository and attribution terms](https://github.com/statsbomb/open-data)
- [Official free-data catalogue](https://statsbomb.com/what-we-do/hub/free-data/)
- [StatsBombPy field examples](https://github.com/statsbomb/statsbombpy)

### football-data.org

- [Current pricing and tier features](https://www.football-data.org/pricing)
- [Team/squad resource](https://docs.football-data.org/general/v4/team.html)
- [API throttling and current-season policy](https://docs.football-data.org/general/v4/policies.html)
- [Terms and graphics restrictions](https://www.football-data.org/client/register)

### TheSportsDB

- [Official API documentation, caps and rate limits](https://www.thesportsdb.com/documentation)
- [Terms of use](https://www.thesportsdb.com/docs_terms_of_use.php)
- [Crowd-sourced database description](https://www.thesportsdb.com/docs_about)

### Sportmonks

- [Current free and paid league coverage](https://www.sportmonks.com/football-api/)
- [Pricing](https://www.sportmonks.com/football-api/plans-pricing/)
- [Current and historical squad endpoint](https://docs.sportmonks.com/v3/endpoints-and-entities/endpoints/team-squads)
- [Player fields and last-updated endpoint](https://docs.sportmonks.com/v3/tutorials-and-guides/tutorials/teams-players-coaches-and-referees/players)

### Reep and OpenFootball

- [Reep identity register, schema and licence](https://github.com/withqwerty/reep)
- [OpenFootball public-domain JSON data](https://github.com/openfootball/football.json)
- [OpenFootball database schema](https://github.com/openfootball/schema.sql)

### Proposed RapidAPI source

- [Creativesdev Free API Live Football Data listing](https://rapidapi.com/Creativesdev/api/free-api-live-football-data)
- [Provider pricing page](https://rapidapi.com/Creativesdev/api/free-api-live-football-data/pricing)
- [RapidAPI subscription, overage and bandwidth guidance](https://docs.rapidapi.com/docs/connecting-to-an-api)
