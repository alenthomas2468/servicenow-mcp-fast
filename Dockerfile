FROM python:3.11-slim

WORKDIR /app

# Copy source code and project config
# README.md is required at build time: pyproject.toml declares it as the
# package's `readme`, and hatchling refuses to build metadata without it.
COPY pyproject.toml README.md .
COPY src/ /app/src/

# Install the package (source is now available)
RUN pip install --no-cache-dir .

# Run as a non-root user (defense in depth: this container holds live
# ServiceNow credentials, so a container-escape bug shouldn't also hand out root)
RUN useradd --create-home mcp
USER mcp

ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV PORT=8080

# Expose port for Streamable HTTP / SSE.
# NOTE: this container serves plain HTTP only. Claude Desktop / claude.ai
# refuse remote MCP servers that aren't HTTPS, so on EC2 this port is never
# exposed directly to the internet — deploy/docker-compose.yml puts the Caddy
# reverse proxy in front of it to terminate TLS. See deploy/Caddyfile.
EXPOSE 8080

# Remote entry point (Streamable HTTP at /mcp by default)
CMD ["servicenow-mcp-http"]
