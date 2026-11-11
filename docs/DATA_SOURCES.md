# Scope and data sources

What the app covers, where each part of the data comes from, and what it does not claim.
The short version is in the [README](../README.md#scope).

## Competitions

All clubs currently present across the Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Eredivisie, Primeira Liga, Belgian Pro League, Turkish Süper Lig and Greek Super League are selectable. The grouped tournament workflow also covers UEFA club competitions, major English/Spanish/German/Italian/Dutch cups and super cups, the Euros, Copa América, AFCON, Asian Cup, FIFA Club World Cup and FIFA World Cup whenever the configured sources publish an edition.

## Seasons

The analytical range is 2021/22–2025/26 plus the live 2026/27 campaign. The July rollover selects five candidate completed seasons; each completed CSV must independently pass full double-round-robin coverage checks. Live rows are clearly labelled as partial and never presented as a completed season.

## App

Dashboard: one typo-tolerant platform search, three domestic analysis modes and ten focused pages grouped as Explore (Overview, Match Centre, League tables, Tournaments), Analyze (Club lab, Players, Analysis lab, Shot lab), Model (Predictions, Model lab) and Data (Data quality, Settings). Match Centre search runs across the filtered data before pagination, and its detail URLs survive reloads. Every listed match opens a factual story with stored statistics, real manager/formation context when published, named goals/cards/substitutions/missed penalties and verified lineup positions and portraits on a responsive pitch. Club head-to-head reads the unified league-and-cup store. The Analysis lab slices domestic and tournament data by competition, edition, team and venue; ranks teams by seven metrics; builds a correlation matrix; analyzes first-half scoring, corners, fouls, cards and referee trends; and exports both the rankings and exact match slice.

## Forecasts

The predictive section serves the walk-forward champion (see Model results above). The Predictions page shows coverage, per-league and per-outcome diagnostics, season-by-season walk-forward results, and a forecast journal that preserves issued probabilities while later filling in actual results; the Model Lab compares every candidate against the base rate and the closing betting line. Long-range forecasts use current known form and cannot anticipate intervening events. Conservative current-points projections provide title shares for all ten domestic leagues.

## Fixture sources

OpenFootball's CC0 data supplies guarded full-season schedules for eight 2026/27 leagues: JSON for E0, SP1, D1, I1, F1, N1 and P1, and Football.TXT (`openfootball/europe`) for the Greek regular season (G1, 182 matches). Each 12-hour cached partition must pass complete double-round-robin, date and club-reconciliation checks before replacing the previous snapshot. Belgium's CC0 file (`openfootball/belgium`) lists all 306 pairings but dates only rounds 1–7 until the Pro League publishes the rest, so it is read and rejected each run and imports automatically once every round is dated. Turkey has no permitted key-less full calendar: OpenFootball has no 2026/27 file, and FixtureDownload's terms allow personal, non-commercial use only (checked 3 October 2026). The optional Football-Data.co.uk weekly CSV remains a six-hour cached nearby-fixture fallback; its checked file had no future rows on 23 September 2026. Both sources' kickoff times are displayed as unverified source times, not converted to a presumed timezone. Data Quality shows future-row coverage by source.

## Tournaments

The tournament adapter loads five completed Champions League seasons (753 matches), the 2025 Club World Cup (64 matches), and the 2018, 2022 and 2026 World Cups (232 matches) from OpenFootball's CC0 repositories without an API key. All three competition families have stage, team, performance, scoring and match-result views. The World Cup view also uses 649 published goal events for scorer, penalty and own-goal analysis.

## The 2026/27 campaign and players

The 2026/27 campaign is integrated into every match-driven page and adds the Eredivisie, Primeira Liga, Belgian Pro League, Turkish Süper Lig and Greek Super League to the core five leagues. Overview shows the selected club's two nearest completed matches and next listed fixture when available; League tables reconstruct live partial standings; Club lab, Shot lab and Match explorer use the same current rows. The player explorer contains 458 tracked 2025/26 player records for the 12 clubs and 4,633 competition-season rows covering appearances, goals, assists, minutes and cards in 41 competitions. These come from the CC0 Transfermarkt Open Dataset, whose update pause and cutoff are visible in the interface. TheSportsDB remains an image and nearby-event fallback. The Catppuccin Mocha interface respects reduced-motion preferences. The app does not claim current 2026/27 squad accuracy, xG or possession.
