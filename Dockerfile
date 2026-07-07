FROM python:3.11-slim

WORKDIR /app

# Copy source code and project config
COPY pyproject.toml .
COPY src/ /app/src/

# Install the package (source is now available)
RUN pip install --no-cache-dir .

# Run as a non-root user
RUN useradd --create-home mcp
USER mcp

ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV PORT=8080

# Expose port for Streamable HTTP / SSE
EXPOSE 8080

# Remote entry point (Streamable HTTP at /mcp by default)
CMD ["servicenow-mcp-http"]
