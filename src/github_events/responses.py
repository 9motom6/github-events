"""Pydantic models for API responses."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TrackedRepos(BaseModel):
    """Response for tracked repositories endpoint."""
    repositories: List[str] = Field(default=[], description="List of repositories that have PR data tracked.", example=["my-org/my-repo"])


class AveragePRTime(BaseModel):
    """Response for average PR time endpoint."""
    repository: str = Field(..., description="The name of the repository.", example="my-org/my-repo")
    average_pr_time_seconds: Optional[float] = Field(default=None, description="The average time in seconds between pull requests.", example=86400.5)


class EventCounts(BaseModel):
    """Response for event counts endpoint."""
    offset_minutes: int = Field(..., description="The time offset in minutes for which the event counts are being reported.", example=60)
    counts: Dict[str, int] = Field(default={}, description="A dictionary of event types and their counts.", example={"WatchEvent": 10, "PullRequestEvent": 5})


class EventConfig(BaseModel):
    """Configuration for event storage."""
    max_per_type: int = Field(..., description="The maximum number of events to keep per event type.", example=10000)
    ttl_hours: float = Field(..., description="The time-to-live in hours for event keys.", example=24)


class EventsStatus(BaseModel):
    """Status of events storage."""
    total: int = Field(..., description="The total number of events stored.", example=15)
    by_type: Dict[str, int] = Field(default={}, description="A dictionary of event types and their counts.", example={"WatchEvent": 10, "PullRequestEvent": 5})
    config: EventConfig = Field(..., description="The event storage configuration.")


class PullRequestRepoStats(BaseModel):
    """Stats for a single repository."""
    count: int = Field(..., description="The number of pull requests tracked.", example=5)
    average_pr_time_seconds: Optional[float] = Field(default=None, description="The average time in seconds between pull requests.", example=86400.5)


class PullRequestsStatus(BaseModel):
    """Status of pull request tracking."""
    repositories_tracked: int = Field(..., description="The number of repositories with pull request data tracked.", example=1)
    repositories: Dict[str, PullRequestRepoStats] = Field(default={}, description="A dictionary of repository names and their pull request stats.")


class Status(BaseModel):
    """Response for status endpoint."""
    events: EventsStatus = Field(..., description="The status of events storage.")
    pull_requests: PullRequestsStatus = Field(..., description="The status of pull request tracking.")
    redis_info: Optional[Dict[str, int]] = Field(default=None, description="Information about the Redis database.", example={"db0": {"keys": 10, "expires": 5}})