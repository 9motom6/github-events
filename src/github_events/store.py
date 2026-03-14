"""Redis implementation of metrics storage for the GitHub event monitor."""

import os
from datetime import datetime, timezone
from typing import Optional
import uuid

import redis

from github_events.responses import (
    EventConfig,
    EventsStatus,
    PullRequestRepoStats,
    PullRequestsStatus,
    Status,
)



class RedisMetricsStore:
    """Redis implementation of metrics storage.

    Uses Redis sorted sets for efficient time-based queries and
    running averages for PR time tracking.
    """

    def __init__(
        self,
        redis_url: str = None,
        redis_client: redis.Redis = None,
        max_events_per_type: int = 10000,
        event_ttl_hours: int = 72,
    ):
        """Initialize the store.

        Args:
            redis_url: Redis connection URL. Defaults to REDIS_URL env var or localhost.
            redis_client: Optional Redis client for dependency injection.
            max_events_per_type: Max events to keep per event type. Older ones are trimmed.
            event_ttl_hours: Hours after which event keys auto-expire.
        """
        if redis_client:
            self._redis = redis_client
        else:
            redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self._redis = redis.from_url(redis_url, decode_responses=True)

        self._max_events_per_type = max_events_per_type
        self._event_ttl_seconds = event_ttl_hours * 3600
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

    def get_tracked_repos(self) -> list[str]:
        """Get list of all repositories that have PR data tracked."""
        repos = []
        for key in self._redis.scan_iter(match="pr:*"):
            data = self._redis.hgetall(key)
            if data and int(data.get("count", 0)) > 0:
                repos.append(key.replace("pr:", ""))
        return sorted(repos)

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
        score = created_at.timestamp()

        # Add event and set TTL
        pipe = self._redis.pipeline()
        pipe.zadd(key, {member: score})
        pipe.expire(key, self._event_ttl_seconds)
        pipe.execute()

        # Trim old events if over limit
        self._trim_events(key)

    def _trim_events(self, key: str) -> None:
        """Remove oldest events if over the max limit."""
        count = self._redis.zcard(key)
        if count > self._max_events_per_type:
            # Remove oldest events (lowest scores)
            to_remove = count - self._max_events_per_type
            self._redis.zremrangebyrank(key, 0, to_remove - 1)

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

    def cleanup(self) -> int:
        """Manually cleanup old events older than TTL.

        Returns:
            Number of keys removed.
        """
        removed = 0
        for key in self._redis.scan_iter(match="events:*"):
            cutoff = datetime.now(timezone.utc).timestamp() - self._event_ttl_seconds
            deleted = self._redis.zremrangebyscore(key, "-inf", cutoff)
            removed += deleted

        # Clean up empty PR keys older than 7 days
        for key in self._redis.scan_iter(match="pr:*"):
            data = self._redis.hgetall(key)
            if data and int(data.get("count", 0)) == 0:
                # No PRs, check if old and delete
                self._redis.delete(key)

        return removed

    def get_status(self, min_pr_count: int = 0) -> Status:
        """Get the current status of the Redis storage.

        Args:
            min_pr_count: Minimum number of pull requests for a repository to be included.

        Returns:
            Status object containing storage status information.
        """
        # Get all event counts
        event_counts = {}
        event_total = 0
        for key in self._redis.scan_iter(match="events:*"):
            count = self._redis.zcard(key)
            event_type = key.replace("events:", "")
            event_counts[event_type] = count
            event_total += count

        # Get all PR repository stats
        pr_stats = {}
        for key in self._redis.scan_iter(match="pr:*"):
            data = self._redis.hgetall(key)
            if data:
                count = int(data.get("count", 0))
                if count >= min_pr_count:
                    repo_name = key.replace("pr:", "")
                    pr_stats[repo_name] = PullRequestRepoStats(
                        count=count,
                        average_pr_time_seconds=float(data.get("running_avg", 0)) if count > 0 else None
                    )

        # Get Redis info if available
        try:
            redis_info = self._redis.info().get("db")
        except Exception:
            redis_info = None

        return Status(
            events=EventsStatus(
                total=event_total,
                by_type=event_counts,
                config=EventConfig(
                    max_per_type=self._max_events_per_type,
                    ttl_hours=self._event_ttl_seconds / 3600
                )
            ),
            pull_requests=PullRequestsStatus(
                repositories_tracked=len(pr_stats),
                repositories=pr_stats
            ),
            redis_info=redis_info
        )