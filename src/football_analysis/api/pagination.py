"""Cursor tokens for match and player list routes."""

from __future__ import annotations

import base64
import json
from typing import Any


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if not cursor:
        return None
    padding = "=" * (-len(cursor) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(cursor + padding))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid cursor") from exc
