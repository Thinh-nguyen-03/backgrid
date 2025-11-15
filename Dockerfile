# Dockerfile for Backgrid API and Workers
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for PostgreSQL
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY src/ ./src/
COPY tests/ ./tests/

# Copy Alembic configuration and migrations
COPY alembic.ini .
COPY migrations/ ./migrations/

# Create non-root user for security
RUN useradd -m -u 1000 backgrid && \
    chown -R backgrid:backgrid /app

# Switch to non-root user
USER backgrid

# Expose API port
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
