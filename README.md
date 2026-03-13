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

### Docker Compose (for production/Portainer)

```bash
docker-compose up --build
```

## API Endpoints

- `GET /wanted_events` - Returns WatchEvent, PullRequestEvent, and IssuesEvent
- `GET /average-pr-time?repository=owner/repo` - Average time between PRs for a repo
- `GET /events-count?offset=10` - Event counts grouped by type for last N minutes

## Assumptions

- Uses GitHub's public event API (https://api.github.com/events) which provides a sample of events
- Events are filtered to only WatchEvent, PullRequestEvent, and IssuesEvent
- Running average formula: Use the formula: $NewAvg = \frac{(OldAvg \times Count) + NewDelta}{Count + 1}$