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

## Data contract

The MVP requires complete domestic league score coverage, not player coverage. Verify each partition's teams, ordered fixture pairs, expected result count, dates, score/result consistency and mandatory fields before replacing database data. Missing optional shots remain NULL. No fabricated demo data is ever loaded in the normal pipeline. Test fixtures are synthetic and isolated to temporary test databases.
