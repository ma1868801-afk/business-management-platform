# Shared base image for the app, ui and indexer services: one dependency set (uv-managed),
# three entrypoints selected by docker-compose's `command`.
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.9 /uv /uvx /usr/local/bin/

WORKDIR /srv

COPY pyproject.toml uv.lock* /srv/
ENV UV_HTTP_TIMEOUT=600
ENV UV_CONCURRENT_DOWNLOADS=4
RUN uv sync --no-dev --no-install-project --verbose

COPY app /srv/app
COPY ui /srv/ui
COPY rag_sources /srv/rag_sources
COPY evaluation /srv/evaluation

# INTEGRATION FIX (RAG_REFACTOR_REPORT.md section 8): `uv sync --no-install-project` means
# the `app` package is never pip-installed into site-packages, so it's importable only via
# the current working directory (`/srv`, set above) being on `sys.path`. `uvicorn app.main:app`
# and `python -m app.rag.indexer` both add the CWD to `sys.path` themselves (`-m` and
# uvicorn's own import machinery do this), so `app` and `ui` happened to work either way --
# but confirmed directly, by actually running it, `chainlit run ui/chainlit_app.py` does
# NOT: it loads that file as a standalone module with no such path adjustment, so
# `ui/chainlit_app.py`'s `from app.config import settings` raised `ModuleNotFoundError` on a
# real run of the `ui` container's exact command. Setting PYTHONPATH explicitly, for every
# service, removes the dependence on each entrypoint tool's own import behavior entirely.
ENV PATH="/srv/.venv/bin:${PATH}" PYTHONUNBUFFERED=1 PYTHONPATH=/srv

# Non-root user (05_security_and_guardrails.md section 13).
RUN useradd --create-home --uid 10001 bmp && chown -R bmp:bmp /srv
USER bmp

# --- app (FastAPI) -------------------------------------------------------------------------
FROM base AS app
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

# --- ui (Chainlit) -------------------------------------------------------------------------
FROM base AS ui
EXPOSE 8000
CMD ["chainlit", "run", "ui/chainlit_app.py", "--host", "0.0.0.0", "--port", "8000", "--headless"]

# --- indexer (one-off job) -----------------------------------------------------------------
FROM base AS indexer
CMD ["python", "-m", "app.rag.indexer"]
