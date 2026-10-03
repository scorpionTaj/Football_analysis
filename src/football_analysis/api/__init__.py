"""FastAPI service over the football analytics store."""

__all__ = ["app", "create_app"]


def __getattr__(name):
    """Do not open the API's read snapshot when importing refresh contracts."""
    if name in __all__:
        from .app import app, create_app
        globals().update(app=app, create_app=create_app)
        return globals()[name]
    raise AttributeError(name)
