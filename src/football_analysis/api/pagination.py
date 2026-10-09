"""Cursor tokens for match and player list routes."""

from __future__ import annotations

import base64
import json
from typing import Any


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None, required: tuple[str, ...] = ()) -> dict[str, Any] | None:
    """Decode a token; anything malformed raises ValueError, which routes map to 400."""
    if not cursor:
        return None
    padding = "=" * (-len(cursor) % 4)
    try:
        token = json.loads(base64.urlsafe_b64decode(cursor + padding))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid cursor") from exc
    if not isinstance(token, dict) or any(key not in token for key in required):
        raise ValueError("Invalid cursor")
    return token
