FROM python:3.14-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml .

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ src/

# Expose port
EXPOSE 8000

# Run the app
CMD ["uv", "run", "uvicorn", "github_events.main:app", "--host", "0.0.0.0", "--port", "8000"]