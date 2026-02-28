FROM python:3.11-slim

WORKDIR /app

# Copy source code and project config
COPY pyproject.toml .
COPY src/ /app/src/

# Install the package (source is now available)
RUN pip install --no-cache-dir .

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Expose port for SSE
EXPOSE 8080

# Default command (can be overridden)
CMD ["python", "src/servicenow_mcp/server_sse.py"]
