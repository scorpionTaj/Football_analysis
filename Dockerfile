# Python image for the API and the scheduler (extract → dbt → models → publish).
FROM python:3.12-slim
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
# data/ (DuckDB, raw CSVs, SQLite fallback) and .env are mounted at runtime, never baked in.
EXPOSE 8000
CMD ["football-api", "--host", "0.0.0.0"]
