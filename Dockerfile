# Python image for the API and the scheduler (extract → dbt → models → publish).
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" MLFLOW_DISABLE_AGENT_HINT=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev --extra de --extra ml
COPY src ./src
COPY warehouse ./warehouse
COPY scripts ./scripts
COPY dagster.yaml ./
RUN uv sync --frozen --no-dev --extra de --extra ml
# Unprivileged runtime user; dbt writes target/ and logs/ under warehouse/. UID 1000 matches the
# usual host owner of the mounted ./data.
RUN useradd --uid 1000 --create-home app && mkdir -p /app/data && chown -R app /app/data /app/warehouse
USER app
# data/ (DuckDB, raw CSVs, SQLite fallback) and .env are mounted at runtime, never baked in.
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"
CMD ["football-api", "--host", "0.0.0.0"]
