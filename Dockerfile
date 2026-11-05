# Agent image for AgentCore Runtime: linux/arm64 (HTTP protocol contract), port 8080.
FROM --platform=linux/arm64 python:3.12-slim
# Runs as a non-root user (docs/aws-hardening, AC6); its home holds the uv cache and the pre-warmed uvx tools.
ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv HOME=/home/app \
    UV_CACHE_DIR=/home/app/.cache/uv PATH="/app/.venv/bin:/home/app/.local/bin:$PATH"
# libexpat1: the rasterio wheel (harness/scenes.py) links it, and the slim base doesn't ship it.
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.13.6 \
    && useradd --uid 10001 --create-home --home-dir /home/app --shell /usr/sbin/nologin app
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY core core
COPY tools tools
COPY agent agent
COPY analysis analysis
COPY harness harness
COPY prompts prompts
RUN uv sync --frozen --no-dev && uv pip install --python /app/.venv/bin/python "aws-opentelemetry-distro==0.22.0" \
    && chown -R app:app /app /home/app
USER app
# Pre-warm the uv cache so a cold start doesn't need PyPI for RODA (design: Tools).
RUN timeout 120 uvx awslabs.roda-mcp-server@0.1.7 --help >/dev/null 2>&1 || true
EXPOSE 8080
CMD ["sh", "agent/boot.sh"]
