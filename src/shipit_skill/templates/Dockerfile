# Container image for the {name} MCP server (stdio transport).
# Built from source so the image always matches the tested code.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir ".[mcp]"

CMD ["{server}"]
