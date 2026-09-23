"""Small persisted freshness gate shared by rate-limited source synchronizers."""

from datetime import datetime, timedelta


def is_fresh(con, key: str, max_age: timedelta | None) -> bool:
    """A completed partition is fresh until its source-specific age expires."""
    row = con.execute(
        "SELECT synced_at FROM source_sync_cache WHERE source=?", [key]
    ).fetchone()
    return bool(row and (max_age is None or row[0] >= datetime.now() - max_age))


def cached_fingerprint(con, key: str) -> str | None:
    row = con.execute(
        "SELECT fingerprint FROM source_sync_cache WHERE source=?", [key]
    ).fetchone()
    return row[0] if row else None


def mark_fresh(con, key: str, fingerprint: str = "") -> None:
    """Call inside the same transaction that publishes the source data."""
    con.execute("DELETE FROM source_sync_cache WHERE source=?", [key])
    con.execute(
        "INSERT INTO source_sync_cache VALUES (?, ?, ?)", [key, fingerprint, datetime.now()]
    )
