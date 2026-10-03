"""Optional, best-effort Redis storage for selected JSON GET responses."""

from __future__ import annotations

import os


class RedisResponseCache:
    def __init__(self, client):
        self.client = client

    @classmethod
    def from_environment(cls) -> RedisResponseCache | None:
        url = os.environ.get("REDIS_URL")
        if not url:
            return None
        try:
            import redis

            client = redis.Redis.from_url(
                url, socket_connect_timeout=0.2, socket_timeout=0.2,
            )
        except (ImportError, ValueError):
            return None
        return cls(client)

    def get(self, key: str) -> bytes | None:
        try:
            return self.client.get(key)
        except Exception:
            # Redis is an optimization; the database remains the source of truth.
            return None

    def set(self, key: str, body: bytes, ttl: int) -> None:
        try:
            self.client.set(key, body, ex=ttl)
        except Exception:
            pass
