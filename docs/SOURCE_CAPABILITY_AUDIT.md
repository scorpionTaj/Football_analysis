# Source capability audit

Audited: 2026-09-23

This audit compares the current `football_analysis` working tree with the publishers' official documentation and repositories. “Available” means a publisher exposes a field or endpoint; it does not imply that the response is complete enough to support a league-wide statistic. The audit treats missing values as unavailable, never as zero.

## Executive finding

The application now uses substantially more than final scores, but it does not yet exploit all valuable free capabilities:

- Football-Data.co.uk match files are the strongest current input for domestic modeling. The app now stores full-time and half-time goals, shots, shots on target, corners, fouls, cards and referee. It still discards kickoff time and all opening/closing market prices, and it does not ingest the separate upcoming-fixture file.
- OpenFootball World Cup-family ingestion now includes the completed 64-match 2025 Club World Cup and stores final/extra-time scores, shootout scores, stages, groups, grounds and goal events. It still discards kickoff/timezone, half-time score and match number and does not use richer `worldcup-full.json` files.
- OpenFootball Champions League ingestion reads only `cl.txt` for five seasons. It keeps dates, stages and scores, but discards kickoff, venue and scorer annotations; the repository's Europa League and Conference League files are unused.
- The Transfermarkt Open Dataset importer now uses six of twelve published tables. `games`, `game_events` and `game_lineups` provide verified managers, formations, officials, stadiums, named goals/cards/substitutions/missed penalties, starting roles, positions and player portraits. Cup matches are normalized into the same tournament store. The snapshot is CC0 but stops before 2026/27.
- TheSportsDB integration calls the free v1 event and media endpoints. It preserves current cup/event metadata when supplied, but its small collection limits mean it remains a current-season enrichment fallback rather than a completeness authority.
- football-data.org is evaluated but not configured. Its free authenticated tier is useful for stable competition/team identities, delayed fixtures and tables, but deep player, lineup, scorer, card and match-statistic data are paid.

## Capability matrix

| Source | Current interface | Used now | Valuable unused capability | Main limit |
| --- | --- | --- | --- | --- |
| Football-Data.co.uk | `mmz4281/{season}/{league}.csv` | Dates, teams, FT/HT goals, shots, shots on target, corners, fouls, cards, referee | Kickoff time; separate upcoming-fixture CSV; optional opening/closing market benchmark | Free downloadable files, not a service-level API; update cadence and field coverage vary; no explicit open-data redistribution licence was found |
| OpenFootball European club tournaments | Season `cl.txt` | Five UCL seasons; date, stage, teams, result and parsed shootout | UCL kickoff/venue/scorers; Europa League; Conference League; qualifying rounds where published | Community-maintained structured text; 2026/27 is not published in the repository at audit time |
| OpenFootball World Cup JSON | Edition `worldcup.json` / `clubworldcup.json` | 2018, 2022 and 2026 World Cups plus all 64 completed 2025 Club World Cup matches; final/ET/shootout scores, stage/group, venue and goals | Kickoff/timezone, half-time scores, match number, full lineups/events/officials; older editions | No availability or live-update SLA; community data; richer fields vary by edition |
| Transfermarkt Open Dataset | Six compressed CSV snapshots | Profiles and season totals plus historical match context, named events, full lineup roles and 4,086 normalized cup matches | Club/valuation/transfer/national-team tables and several secondary fields | CC0 snapshot paused at 6 July 2026; 2026/27 squads absent |
| TheSportsDB free v1 | Ten endpoints using public key `123` | Media; capped profiles/stats/tables; one previous/next league event; cached and rendered event stats/timeline/lineup samples | Honours/former teams/contracts; venue/equipment; optional TV/highlights | 30 requests/minute and small endpoint result caps; v2 and live scores are premium; crowd-sourced completeness |
| football-data.org free v4 | Not configured | None | Stable IDs/emblems, competitions/seasons, delayed fixtures/results and full league tables | Token required; 12 competitions; 10 calls/minute; live and deep data paid |

## 1. Football-Data.co.uk

### Current code use

`src/football_analysis/adapters.py` loads season CSV files and now normalizes:

`Div`, `Date`, `HomeTeam`, `AwayTeam`, `FTHG`, `FTAG`, `FTR`, `HTHG`, `HTAG`, `HS`, `AS`, `HST`, `AST`, `HC`, `AC`, `HF`, `AF`, `HY`, `AY`, `HR`, `AR`, and `Referee`.

The match and current-season tables preserve these fields. The analysis service uses them for first/second-half scoring, attempts, discipline, corners and referee analysis. Coverage is correctly nullable because some leagues or historical partitions omit match statistics.

### Available but unused

| Capability | Evidence in the published files | Recommended use |
| --- | --- | --- |
| Kickoff time | `Time` | Store the source clock time without inferring a timezone; add timezone-labelled ordering only if a future source verifies the zone. Dates alone can misorder same-day games. |
| Half-time result code | `HTR` | No new field is required because it is derivable from the stored half-time goals. Validate it during ingestion as an integrity check. |
| Opening/closing prices | Home/draw/away, totals and Asian-handicap columns, with `C` variants for closing prices | Keep in an isolated optional research table. Convert to overround-adjusted probabilities and use only as a benchmark for model calibration. Do not mix betting data into the default performance experience. |
| Upcoming fixtures | OpenFootball `football.json` plus `fixtures.csv` | Seven current-season full league calendars are now guarded by complete-pair, date and identity checks; the weekly CSV remains a nearby fallback for all ten leagues. Neither source guarantees final kickoff times or supplies all domestic cups. |
| Additional countries/divisions | Country pages and “all new countries” downloads | Add only through the competition manifest and the same completeness validation; this is lower priority than improving the ten current leagues. |

The current local files do **not** contain expected-goals columns, so the application must not label shots or a home-grown estimate as provider xG. Any future xG field requires a separately verified source and explicit coverage reporting.

### Quota, licence and completeness

Football-Data.co.uk publishes free CSV downloads rather than an authenticated JSON API and states that the data is free. The site gives a dated weekly fixture file and describes when weekend and midweek odds are normally collected. It does not publish a request quota or service-level agreement. No explicit CC/open-data licence for redistribution was found in its official pages, so the project should cite the publisher, retain source URLs and hashes, cache conservatively, and re-check permission before redistributing the raw archive as part of a public product. The publisher also disclaims correctness, making local validation and visible coverage essential.

Primary sources: [data-download catalogue](https://www.football-data.co.uk/data.php), [field definitions and acknowledgements](https://www.football-data.co.uk/notes.txt), [weekly fixtures and update cadence](https://www.football-data.co.uk/matches.php), [extra league catalogue](https://www.football-data.co.uk/all_new_data.php), and [accuracy disclaimer](https://www.football-data.co.uk/disclaimer.php).

## 2. OpenFootball

Both repositories used here publish their data under CC0/public-domain terms and require no API key. They are static/community-maintained files, not guaranteed live services.

### World Cup JSON

The current parser uses:

- `round`, `date`, `team1`, `team2`, `group`, and `ground`;
- `score.ft`, preferring `score.et` where applicable, plus `score.p`;
- `goals1` and `goals2`, including scorer, minute, penalty and own-goal flags.

The scorer events are stored in `tournament_goals` and rendered in the tournament experience. Still unused from the basic file are `time`, its timezone suffix, `score.ht`, and `num`.

The repository also publishes `worldcup-full.json`. The documented full format adds starting XI, bench, substitutions, bookings, referees and penalty-shootout detail. These are analytically useful, but they belong in normalized event, lineup and official tables rather than extra JSON columns on a match row. Field presence should be measured by edition.

The same repository includes a completed 2025 FIFA Club World Cup file. It can be added as a new competition manifest entry without another provider.

Recommended next data additions:

1. Preserve kickoff/timezone, half-time scores and match number from the basic JSON.
2. Ingest `worldcup-full.json` behind a versioned parser into match-event, lineup and official tables.
3. Add the 2025 Club World Cup.
4. Expand older World Cups only when a product view needs them; the current three-edition scope already covers recent modeling.

Primary sources: [World Cup JSON repository and schema examples](https://github.com/openfootball/worldcup.json), [2026 basic JSON](https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json), [2026 full JSON](https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup-full.json), [2025 Club World Cup JSON](https://raw.githubusercontent.com/openfootball/worldcup.json/master/2025/clubworldcup.json), and [CC0 licence](https://github.com/openfootball/worldcup.json/blob/master/LICENSE.md).

### European club tournaments

The current adapter reads only Champions League `cl.txt` for 2021/22 through 2025/26. It extracts date, stage, teams, final score and a limited shootout suffix. It does not preserve the text file's kickoff, `@ venue`, scorer/minute annotations, own goals, penalties, aggregate notes or leg relationships.

The same repository advertises Champions League including qualifiers, Europa League and Conference League. Use a competition manifest with repository path, filename, season range and parser version. This avoids conditionals in the dashboard and makes incomplete partitions explicit.

Recommended next data additions:

1. Make the UCL parser preserve kickoff, venue, leg number, aggregate result and scorer events where present.
2. Add Europa League and Conference League as manifest entries after validating every requested season/file.
3. Do not invent a 2026/27 partition: the repository lists seasons only through 2025/26 at the audit date.

Primary sources: [European tournament repository and coverage](https://github.com/openfootball/champions-league) and [CC0 licence](https://github.com/openfootball/champions-league/blob/master/LICENSE.md).

## 3. Transfermarkt Open Dataset

### Current code use

`src/football_analysis/open_players.py` downloads six compressed CSVs: `players`, `games`, `appearances`, `competitions`, `game_events`, and `game_lineups`. It limits the standalone player explorer to 12 featured clubs, derives competition-season totals, and materializes match detail for every mapped game. The current snapshot produced 335,270 named timeline rows, 855,237 lineup rows and 4,086 domestic, continental and international cup matches.

The profile view uses name, broad/sub-position, nationality, date of birth, preferred foot, height, current and highest market value, portrait URL and profile URL. Match Centre additionally uses manager, formation, stadium, attendance, referee, named goal/card/substitution/missed-penalty events, starting/bench roles, positions, shirt numbers and portraits. The competition map groups cups separately from domestic leagues.

### Published tables versus use

The publisher documents 12 joinable tables and also ships a single ready-to-query DuckDB snapshot.

| Published table | Current use | High-value unused analysis |
| --- | --- | --- |
| `competitions` | Stable app-code mapping and domestic/continental/international grouping | Additional geography and hierarchy fields |
| `clubs` | Not downloaded | All covered clubs, squad size, average age, foreign-player share, total value, coach, stadium capacity |
| `players` | 12-club current snapshot | All historical identities, contract/agent fields, national-team link, international caps/goals |
| `games` | Season/date, score, round, managers, formations, stadium, attendance and referee | Aggregate score and pre-match positions |
| `appearances` | Aggregated totals | Per-match availability, minutes, contributions and discipline features |
| `player_valuations` | Not downloaded | Time-safe value curves, player development and squad-value trends |
| `club_games` | Not downloaded | Team-centric opponent, manager and table-position context |
| `game_events` | Named goals, assists, cards, substitutions, shootout goals and missed penalties | Richer event-detail taxonomy and derived lineup-continuity features |
| `game_lineups` | Starter/bench status, position, shirt number and player portrait | Captaincy and derived lineup-continuity features |
| `transfers` | Not downloaded | Arrivals, departures, fees, value at transfer and net spend |
| `countries` | Not downloaded | Country/confederation dimension |
| `national_teams` | Not downloaded | National-team identities, squad size and FIFA ranking |

The six-file importer preserves publisher IDs and materializes only the fields required by the product contract. A direct published-DuckDB adapter remains an option if the remaining tables are later needed.

### Quota, licence and completeness

There is no API request quota; the project publishes downloadable DuckDB and compressed CSV snapshots. The repository applies CC0 1.0 to the dataset. CC0 does not clear third-party trademark, portrait, privacy or publicity rights, so external image URLs must remain separately reviewed.

The publisher says updates are paused and explicitly reports these cutoffs: games through 2026-07-06, appearances through 2026-06-28 and valuations through 2026-06-12; 2026/27 squads are absent. This source is strong for historical features and training, but cannot define current squads. All joins for predictions must use the last value, lineup, manager or transfer known **before** kickoff to prevent future information leakage.

Primary sources: [repository, scale, table inventory and update status](https://github.com/dcaribou/transfermarkt-datasets), [published data dictionary](https://github.com/dcaribou/transfermarkt-datasets/blob/master/data/prep/dataset-metadata.json), and [CC0 licence](https://github.com/dcaribou/transfermarkt-datasets/blob/master/LICENSE).

## 4. TheSportsDB free v1

### Endpoint inventory used by the code

The public v1 key is `123`. The official rate limit is 30 requests per minute. Free endpoints also cap the number of returned rows, often far below a complete league, squad, lineup or event timeline.

| Endpoint | Current purpose | Documented free result limit | Product status |
| --- | --- | ---: | --- |
| `searchteams.php` | Resolve configured club name to provider ID and media | 1 | Used |
| `lookupleague.php` | Competition identity/media | 1 | Used |
| `lookuptable.php` | Reference standings | 5 | Used and explicitly partial |
| `lookup_all_players.php` | Player profiles | 10 | Used and explicitly capped |
| `lookupplayerstats.php` | Player statistic rows | 10 | Used as supplemental data |
| `eventspastleague.php` | Previous league spotlight | 1 | Used; not a complete recent-results feed |
| `eventsnextleague.php` | Next league spotlight | 1 | Used; not a fixture list |
| `lookupeventstats.php` | Selected recent-event statistics | 5 | Ingested, cached and rendered with source metadata |
| `lookuptimeline.php` | Selected recent-event timeline | 5 | Ingested, cached and rendered as a capped sample |
| `lookuplineup.php` | Selected recent-event lineup | 5 | Ingested, cached and rendered as a capped sample |

The provider event-detail adapter remains explicitly capped. Match Centre prefers the complete historical Transfermarkt rows when a game is mapped, and labels TheSportsDB-only rows as provider samples instead of presenting them as a full formation or event history.

### Useful free v1 capabilities still unused

| Endpoint group | Examples | Free limits | Decision |
| --- | --- | --- | --- |
| Event identity/results | `lookupevent.php`, `eventresults.php` | 1 / 5 | Add `lookupevent.php` to preserve event status, kickoff, venue and artwork for the detail drawer. `eventresults.php` is lower priority for football. |
| Player history | `lookupplayer.php`, `lookuphonours.php`, `lookupformerteams.php`, `lookupmilestones.php`, `lookupcontracts.php`, `playerresults.php` | 1 or 5 | Useful for an on-demand profile drawer; cache permanently by provider ID and show returned-count limits. |
| Team/venue content | `lookupteam.php`, `lookupequipment.php`, `lookupvenue.php` | 1 or 2 | Add stadium and kit history only if the team-detail page needs them. Keep artwork rights metadata. |
| Discovery/reconciliation | `searchplayers.php`, `searchvenues.php`, `search_all_seasons.php`, `search_all_teams.php`, `search_all_leagues.php` | 1, 5 or 10 | Useful for an admin identity-mapping tool, never for proving complete membership. |
| Schedules | `eventsnext.php`, `eventslast.php`, `eventsday.php`, `eventsseason.php` | 1, 3 or 15 | Do not replace the primary match store with capped data. `eventsday.php` may power a labelled daily spotlight. |
| Broadcast/video | `lookuptv.php`, `eventstv.php`, `eventshighlights.php` | 1 or 2 | Optional editorial content; lower analytical value and subject to geolocation/link availability. |

### Terms and reliability

TheSportsDB describes itself as crowd-sourced. Its terms permit copying and modifying content returned by official API endpoints, prohibit scraping the website, restrict app-store publication on the free plan, prohibit API resale, require trademarked logos to remain unmodified, and advise checking the `strCreativeCommons` flag for player artwork. The project should preserve attribution and rights metadata for every external asset.

All calls should pass through one quota-aware, cached client recording endpoint, parameters, fetch time, response count and completeness label. The Next.js client must never fan out provider requests while rendering a page.

Primary sources: [v1 documentation, endpoint caps and rate limit](https://www.thesportsdb.com/documentation), [crowd-sourced database description](https://www.thesportsdb.com/docs_about), [terms of use](https://www.thesportsdb.com/docs_terms_of_use.php), and [artwork types](https://www.thesportsdb.com/docs_artwork).

## 5. Optional football-data.org v4

football-data.org is not currently called by the application, so it has no unexploited local endpoint. It remains a useful optional authenticated adapter if a user supplies a free token.

The current free plan provides 12 competitions, delayed scores/schedules, fixtures, league tables and 10 calls per minute. The free competition list includes Champions League, World Cup, Premier League, Primeira Liga, Eredivisie, Bundesliga, Ligue 1, Serie A and La Liga. Of this app's ten domestic leagues, Belgian, Turkish and Greek top flights are outside the displayed free list.

Useful free resources for this project are:

- competition and season identity, including stable IDs, area, emblem, season dates, stages and winners;
- team identity and crests for covered competitions;
- delayed match/fixture schedules;
- complete league tables for covered leagues.

Do not build a free-only feature around live scores, lineups, substitutions, goal scorers, cards, squads, odds or match statistics. The pricing page places live/deep data and the statistics add-on in paid packages. Unauthenticated clients receive only area and competition-list access, capped at 100 requests per 24 hours; registered free clients receive 10 requests per minute.

If added, use football-data.org for identity reconciliation and delayed fixture/table validation, not as a required replacement for the CC0 and public-file baseline. Store the provider IDs in mapping tables rather than exposing provider-specific IDs as domain keys.

Primary sources: [free-tier pricing](https://www.football-data.org/pricing), [free competition coverage](https://www.football-data.org/coverage), [competition resource](https://docs.football-data.org/general/v4/competition.html), and [request policy](https://docs.football-data.org/general/v4/policies.html).

## Implementation order for remaining free capabilities

1. Maintain OpenFootball's seven validated full-season calendars and seek a permitted fuller source for Belgium, Turkey and Greece; retain timestamps and reconciliation.
2. Preserve World Cup-family kickoff, timezone, half-time score and match number.
3. Add OpenFootball full-detail World Cup lineups/events/officials with field coverage by edition.
4. Improve OpenFootball European parsing for kickoff, venue, leg and scorer annotations; historical Europa League and Conference League coverage now comes from the normalized Transfermarkt snapshot.
5. Add valuations and transfers only when their lifecycle and storage costs are justified; match events and lineups are already materialized.
6. Build time-safe feature views for rolling form, Elo, attempts, discipline, rest, home advantage, lineup continuity, manager tenure and valuation available before kickoff.
7. Add football-data.org only as an optional token-based identity and delayed-fixture/table validator.

## Prediction consequences

The audited sources support classical probabilistic match modeling more reliably than deep learning at the current data volume. Start with an Elo/logistic home-draw-away model and an independent-Poisson goals model. Add tree-based models only after time-safe feature coverage is verified. Deep learning should wait for much larger event/lineup history.

Every model must:

- split training and validation chronologically;
- derive rolling features strictly from matches before the predicted kickoff;
- join valuation, transfer, manager and lineup data as of kickoff;
- publish multiclass log loss, Brier score and calibration alongside accuracy;
- display model version, training cutoff, feature coverage and uncertainty;
- treat market probabilities, if enabled, as a separately labelled benchmark.

This sequence exploits the strongest unused free data without making the product depend on a small proprietary quota or presenting capped enrichment as complete analysis.
