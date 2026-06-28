# Codebase Architect — runs the REST API.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CA_DATA_DIR=/data \
    CA_WORKSPACES_DIR=/workspaces \
    CA_LOG_JSON=true \
    CA_PORT=47800

# git is an optional capability (remote Git sources); everything else works without it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY plugins ./plugins

# Core + CLI + API + all AI providers (Claude, OpenAI/OpenRouter/local, Gemini),
# plus the example HTML renderer plugin.
RUN pip install ".[cli,api,ai,ai-openai,ai-gemini]" "./plugins/html_site"

RUN useradd --create-home app \
    && mkdir -p /data /workspaces \
    && chown -R app:app /data /workspaces
USER app

# Internal listen port. Non-standard default to avoid clashing with other
# services; override with CA_PORT at runtime (the deploy compose's CONTAINER_PORT).
EXPOSE 47800

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os,urllib.request,sys; p=os.environ.get('CA_PORT','47800'); \
sys.exit(0 if urllib.request.urlopen(f'http://localhost:{p}/health').status==200 else 1)"

# Shell form so ${CA_PORT} is expanded at container start.
CMD architect serve --host 0.0.0.0 --port "${CA_PORT}"
