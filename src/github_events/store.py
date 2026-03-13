"""Redis implementation of metrics storage for the GitHub event monitor."""

import os
from datetime import datetime, timezone
from typing import Optional
import uuid

import redis


class RedisMetricsStore:
    """Redis implementation of metrics storage.

    Uses Redis sorted sets for efficient time-based queries and
    running averages for PR time tracking.
    """

    def __init__(self, redis_url: str = None):
        """Initialize the store.

        Args:
            redis_url: Redis connection URL. Defaults to REDIS_URL env var or localhost.
        """
        redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._event_counter = 0

    def add_pull_request(self, repo_name: str, created_at: datetime) -> None:
        """Record a pull request event for calculating average time between PRs."""
        key = f"pr:{repo_name}"
        prev_data = self._redis.hgetall(key)

        if not prev_data:
            self._redis.hset(key, mapping={
                "last_pr_time": str(created_at.timestamp()),
                "running_avg": "0",
                "count": "0"
            })
            return

        last_pr_time = float(prev_data["last_pr_time"])
        running_avg = float(prev_data["running_avg"])
        count = int(prev_data["count"])

        delta_seconds = created_at.timestamp() - last_pr_time

        if count == 0:
            new_avg = delta_seconds
        else:
            new_avg = (running_avg * count + delta_seconds) / (count + 1)

        self._redis.hset(key, mapping={
            "last_pr_time": str(created_at.timestamp()),
            "running_avg": str(new_avg),
            "count": str(count + 1)
        })

    def get_average_pr_time(self, repo_name: str) -> Optional[float]:
        """Get the average time between pull requests for a repository."""
        key = f"pr:{repo_name}"
        data = self._redis.hgetall(key)

        if not data or int(data["count"]) == 0:
            return None

        return float(data["running_avg"])

    def add_event(self, event_type: str, created_at: datetime) -> None:
        """Record an event for offset-based counting."""
        key = f"events:{event_type}"
        # Use UUID to ensure unique members even with same timestamp
        member = f"{created_at.timestamp()}:{uuid.uuid4()}"
        self._redis.zadd(key, {member: created_at.timestamp()})

    def get_event_counts_by_type(self, offset_minutes: int) -> dict[str, int]:
        """Get event counts grouped by type for the given time offset."""
        cutoff = datetime.now(timezone.utc).timestamp() - (offset_minutes * 60)

        counts = {}
        for key in self._redis.scan_iter(match="events:*"):
            event_type = key.replace("events:", "")
            count = self._redis.zcount(key, cutoff, "+inf")
            if count > 0:
                counts[event_type] = count

        return counts