# Codebase Architect — runs the REST API.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CA_DATA_DIR=/data \
    CA_WORKSPACES_DIR=/workspaces \
    CA_LOG_JSON=true

# git is an optional capability (remote Git sources); everything else works without it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY plugins ./plugins

# Core + CLI + API + Claude provider, plus the example HTML renderer plugin.
RUN pip install ".[cli,api,ai]" "./plugins/html_site"

RUN useradd --create-home app \
    && mkdir -p /data /workspaces \
    && chown -R app:app /data /workspaces
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["architect", "serve", "--host", "0.0.0.0", "--port", "8000"]
