# GitHub Event Monitor

Streams GitHub events from the public event firehose and provides metrics via REST API.

## Quick Start

### Prerequisites

- Python 3.14+
- Redis

### Development

1. Start Redis locally:
   ```bash
   docker run -p 6379:6379 redis:7-alpine
   ```

2. Run the app:
   ```bash
   uv run uvicorn github_events.main:app --reload
   ```

## Deployment

There are two ways to deploy this application using Docker Compose.

### Local Development

The provided `docker-compose.yml` is configured for local development. It will build the Docker image locally and mount the source code, allowing for hot-reloading.

```bash
docker-compose up --build
```

### Production Deployment (using pre-built image)

For production, it's recommended to use a pre-built Docker image from a container registry like GitHub Container Registry.

1.  **Create a `docker-compose.prod.yml` file with the following content:**

    ```yaml
    services:
      redis:
        image: redis:7-alpine
        command: >
          redis-server 
          --maxmemory 3gb 
          --maxmemory-policy allkeys-lru
        ports:
          - "6379:6379"
        volumes:
          - redis_data:/data
        healthcheck:
          test: ["CMD", "redis-cli", "ping"]
          interval: 5s
          timeout: 3s
          retries: 5

      app:
        image: ghcr.io/9motom6/github-events:latest
        ports:
          - "8000:8000"
        environment:
          - REDIS_URL=redis://redis:6379/0
        depends_on:
          redis:
            condition: service_healthy

    volumes:
      redis_data:
    ```

2.  **Run Docker Compose:**

    ```bash
    docker-compose -f docker-compose.prod.yml up -d
    ```

## API Endpoints

- `GET /wanted_events` - Returns WatchEvent, PullRequestEvent, and IssuesEvent
- `GET /average-pr-time?repository=owner/repo` - Average time between PRs for a repo
- `GET /events-count?offset=10` - Event counts grouped by type for last N minutes

## Assumptions

- Uses GitHub's public event API (https://api.github.com/events) which provides a sample of events
- Events are filtered to only WatchEvent, PullRequestEvent, and IssuesEvent
- Running average formula: Use the formula: $NewAvg = \frac{(OldAvg \times Count) + NewDelta}{Count + 1}$