FROM ubuntu:24.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    nodejs \
    npm \
    git \
    curl \
    wget \
    sqlite3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Node 20 (LTS) for Astro
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Set up Python virtual environment
RUN python3.12 -m venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Working directory
WORKDIR /app

# Copy application code
COPY . /app

# Create data directories
RUN mkdir -p \
    /app/projects/the-llm-report/data/chroma \
    /app/logs/bridge \
    /app/bridge/inbox \
    /app/bridge/outbox \
    /app/bridge/processed \
    /app/outputs

# Set permissions
RUN chmod -R 755 /app/bridge/cli/ || true

# Expose LiteLLM proxy port (internal only)
EXPOSE 4000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import sqlite3; sqlite3.connect('/app/projects/the-llm-report/data/cost_log.sqlite')" || exit 1

CMD ["python3", "scripts/run-pipeline.sh"]
