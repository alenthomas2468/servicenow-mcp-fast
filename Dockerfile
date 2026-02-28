FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY src/ /app/src/

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Expose port for SSE
EXPOSE 8080

# Default command (can be overridden)
CMD ["python", "src/servicenow_mcp/server_sse.py"]
