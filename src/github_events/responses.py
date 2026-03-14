"""Pydantic models for API responses."""

from typing import Dict, List, Optional

from pydantic import BaseModel


class TrackedRepos(BaseModel):
    """Response for tracked repositories endpoint."""
    repositories: List[str] = []


class AveragePRTime(BaseModel):
    """Response for average PR time endpoint."""
    repository: str
    average_pr_time_seconds: Optional[float] = None


class EventCounts(BaseModel):
    """Response for event counts endpoint."""
    offset_minutes: int
    counts: Dict[str, int] = {}


class EventConfig(BaseModel):
    """Configuration for event storage."""
    max_per_type: int
    ttl_hours: float


class EventsStatus(BaseModel):
    """Status of events storage."""
    total: int
    by_type: Dict[str, int] = {}
    config: EventConfig


class PullRequestRepoStats(BaseModel):
    """Stats for a single repository."""
    count: int
    average_pr_time_seconds: Optional[float] = None


class PullRequestsStatus(BaseModel):
    """Status of pull request tracking."""
    repositories_tracked: int
    repositories: Dict[str, PullRequestRepoStats] = {}


class Status(BaseModel):
    """Response for status endpoint."""
    events: EventsStatus
    pull_requests: PullRequestsStatus
    redis_info: Optional[Dict[str, int]] = None