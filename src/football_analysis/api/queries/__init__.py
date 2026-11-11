"""Database reads that power the versioned API.

One module per area of the app; everything the API calls is re-exported here, so
`queries.catalog(store)` and `from ...queries import list_matches` keep working.
"""

from football_analysis.api.queries.reference import (
    API_SCHEMA_REVISION,
    catalog,
    health,
    list_teams,
    snapshot_etag,
)
from football_analysis.api.queries.matches import (
    event_detail,
    list_event_details,
    list_matches,
    load_match_source_rows,
    match_centre_detail,
    shot_analysis,
)
from football_analysis.api.queries.analysis import (
    build_analysis,
    standings,
    tournament,
)
from football_analysis.api.queries.players import (
    get_player,
    list_players,
    list_transfers,
)
from football_analysis.api.queries.forecasts import (
    LIVE_FORECAST_SQL,
    models,
    predictions,
)
from football_analysis.api.queries.overview_page import (
    overview,
)
from football_analysis.api.queries.operations import (
    pipeline,
    quality,
)

__all__ = [
    "API_SCHEMA_REVISION",
    "LIVE_FORECAST_SQL",
    "build_analysis",
    "catalog",
    "event_detail",
    "get_player",
    "health",
    "list_event_details",
    "list_matches",
    "list_players",
    "list_teams",
    "list_transfers",
    "load_match_source_rows",
    "match_centre_detail",
    "models",
    "overview",
    "pipeline",
    "predictions",
    "quality",
    "shot_analysis",
    "snapshot_etag",
    "standings",
    "tournament",
]
