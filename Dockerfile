# Agent image for AgentCore Runtime: linux/arm64 (HTTP protocol contract), port 8080.
FROM --platform=linux/arm64 python:3.12-slim
ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv PATH="/app/.venv/bin:/root/.local/bin:$PATH"
RUN pip install --no-cache-dir uv==0.13.6
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY core core
COPY tools tools
COPY agent agent
COPY analysis analysis
COPY harness harness
COPY prompts prompts
RUN uv sync --frozen --no-dev && uv pip install --python /app/.venv/bin/python "aws-opentelemetry-distro>=0.18.0"
# Pre-warm the uv cache so a cold start doesn't need PyPI for RODA (design: Tools).
RUN timeout 120 uvx awslabs.roda-mcp-server@0.1.7 --help >/dev/null 2>&1 || true
EXPOSE 8080
CMD ["sh", "agent/boot.sh"]
