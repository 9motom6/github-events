FROM python:3.14-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files first (better caching)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy the entire source directory
# This will result in /app/src/github_events/...
COPY src/ ./src/

# Set PYTHONPATH so 'import github_events' works
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8000

# Run the app
# Note: Pointing uvicorn to github_events.main:app
CMD ["uv", "run", "uvicorn", "github_events.main:app", "--host", "0.0.0.0", "--port", "8000"]