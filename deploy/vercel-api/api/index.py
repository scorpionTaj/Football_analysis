"""Vercel Python function: the whole FastAPI app behind one route (see vercel.json)."""

from football_analysis.api.app import app

__all__ = ["app"]
