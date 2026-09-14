"""Read-only FastAPI service over DuckDB analytics."""

from .app import app, create_app

__all__ = ["app", "create_app"]
