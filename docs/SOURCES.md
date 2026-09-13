# Source research — 10 September 2026

## Selected: Football-Data.co.uk historical CSV

Primary source: https://www.football-data.co.uk/data
Historical country index: https://www.football-data.co.uk/englandm.php
Field definitions: https://www.football-data.co.uk/notes.txt
Example tested endpoint: https://www.football-data.co.uk/mmz4281/2526/E0.csv

The provider describes its historical results, match statistics and odds files as free downloadable CSV/Excel, updated at least twice weekly. No token is required by the tested CSV endpoint. E0, SP1, D1, I1 and F1 are the five selected league codes. This implementation consumes scores and selected shots fields, not betting prices. Public files are data endpoints, not a guaranteed versioned API.

No published numerical CSV quota or explicit broad redistribution grant was verified. The implementation uses sequential downloads, a one-second courtesy pause, persistent caching, bounded retries with Retry-After support, and no scraping or access-control bypasses. Page requests through the research browser encountered redirects/429 responses, but the actual CSV endpoint was separately tested. Free access is not treated as an open-data licence; source attribution is present in the dashboard. Review current terms before raw-data redistribution or commercial hosting.

## Evaluated: football-data.org

Primary pricing: https://www.football-data.org/pricing
Competition documentation: https://docs.football-data.org/general/v4/competition.html

The pricing page lists a €0 tier with 12 competitions, delayed scores/schedules, fixtures and league tables at 10 calls/minute. Ten seasons of history are listed in a paid ML package, while lineups, scorers and squads appear in paid deep-data tiers. Consequently five-season/player coverage is not assumed available free, and this app does not depend on this provider. No paid endpoint, account or token was configured.

## Evaluated: StatsBomb Open Data

Primary repository: https://github.com/hudl/open-data

Offers selected competitions/seasons, match JSON, events and lineups, plus selected 360 data. Its README requires StatsBomb attribution and logo when publishing resulting research/insights. Selection is not equivalent to complete recent coverage for all 12 clubs; it is a candidate for a separately labelled event-analysis module, not a fallback that fabricates full coverage. Inspect the repository licence and actual competition catalogue before adding it.

## Added: TheSportsDB capped supplemental feed

Documentation: https://www.thesportsdb.com/documentation
Terms: https://www.thesportsdb.com/docs_terms_of_use.php

The documented v1 free key is 123, with 30 requests per minute. Historical soccer tables accept league and season parameters. The free lookup-table response is capped at five rows, which live verification confirmed. League past/next event calls return one event, team player lists return up to 10 players, and player statistics return up to 10 rows per player on the free tier. The app stores these as explicitly capped supplemental data beside complete results-derived tables. It does not call the feed official or imply complete standings, fixture, squad or player-season coverage. API use is permitted by the provider's terms; website scraping is prohibited and is not used.

The same documented API responses expose image URLs for players, teams and leagues. Iteration 2.3 caches the metadata for 12 featured club badges and 10 competition badges. Images remain hosted by TheSportsDB and are rendered from validated HTTPS URLs; synchronization is explicit and never runs on a dashboard page view.

Current-season completed results use Football-Data.co.uk codes E0, SP1, D1, I1, F1, N1, P1, B1, T1 and G1. Incomplete future fixtures are excluded rather than treated as failed results. TheSportsDB contributes one latest and one next listed event per league so the UI can show a fresher headline result and a limited upcoming fixture without overstating fixture coverage.

## Player-source decision

See PLAYER_DB_RESEARCH.md for the current comparison. The completed-season player explorer now uses the published CC0 Transfermarkt dataset for all tracked 2025/26 player records at the 12 featured clubs and aggregates only source-returned appearances. Current 2026/27 squads remain a separate feature gate because the dataset's automated updates paused on 6 July 2026.

## Added: Transfermarkt Open Dataset snapshot

Repository and update status: https://github.com/dcaribou/transfermarkt-datasets
Published metadata and schema: https://github.com/dcaribou/transfermarkt-datasets/blob/master/data/prep/dataset-metadata.json
Licence: https://github.com/dcaribou/transfermarkt-datasets/blob/master/LICENSE

The project publishes compressed CSV tables under CC0 1.0. The imported snapshot contains 458 tracked players whose `current_club_id` maps to one of the 12 featured clubs and whose `last_season` is 2025. Appearance rows are joined to games and competitions, restricted to seasons 2021 through 2025, and aggregated into 4,633 player/season/competition rows. The latest included match date is 28 June 2026. Goals, assists, minutes and cards remain zero only when the source appearance row explicitly contains zero; absent players or matches are not synthesized.

The dataset's external portrait URLs are references to third-party media. Their presence in the CC0 metadata does not establish copyright permission for the underlying photographs. The dashboard hotlinks validated HTTPS references for personal display and prefers existing TheSportsDB artwork when available; any public deployment must review media rights separately.

The upstream repository states that automated updates are paused as of 6 July 2026 and that 2026/27 squads are not covered. The dashboard labels the snapshot and cutoff. API-Football is the researched optional current-squad source because its official free plan offers 100 calls per day and a squad endpoint, but it requires a user key, a live coverage preflight and a separate publication-rights review before activation.

## Evaluated: Free API Live Football Data on RapidAPI

Listing and pricing: https://rapidapi.com/Creativesdev/api/free-api-live-football-data/pricing
RapidAPI subscription guidance: https://docs.rapidapi.com/docs/connecting-to-an-api

The listing advertises fixtures, live events, standings, teams, players, lineups, statistics, heatmaps and incidents. Live pricing inspection on 13 September 2026 showed a Basic plan at $0 with a hard limit of 100 requests per month and a nominal 1,000 requests/hour rate limit. Paid plans begin at $9.99/month for 20,000 requests. RapidAPI also documents that plan subscriptions can carry quota and bandwidth charges.

The 100-request monthly limit is too small to replace the current historical ingestion, ten-league current-season refresh, 12-club player sync and artwork cache. A complete switch would also introduce an account-bound RapidAPI key and a single-provider dependency. The project therefore keeps Football-Data.co.uk for complete historical/current CSV results and TheSportsDB for explicitly capped supplemental data and artwork. A future RapidAPI adapter may be added behind an environment variable for optional live-match detail, but it must not become required for the no-paid baseline.

## Data contract

The MVP requires complete domestic league score coverage, not player coverage. Verify each partition's teams, ordered fixture pairs, expected result count, dates, score/result consistency and mandatory fields before replacing database data. Missing optional shots remain NULL. No fabricated demo data is ever loaded in the normal pipeline. Test fixtures are synthetic and isolated to temporary test databases.
