"""FastAPI route handlers."""

from fastapi import APIRouter, Depends, Query

from github_events.dependencies import get_store
from github_events.responses import (
    AveragePRTime,
    EventCounts,
    Status,
    TrackedRepos,
)
from github_events.store import RedisMetricsStore

router = APIRouter()


@router.get("/average-pr-time", tags=["Github Event Monitor"])
async def average_pr_time(
    repository: str, store: RedisMetricsStore = Depends(get_store)
) -> AveragePRTime:
    """Calculate the average time between pull requests for a given repository."""
    avg_time = store.get_average_pr_time(repository)
    return AveragePRTime(repository=repository, average_pr_time_seconds=avg_time)


@router.get("/events-count", tags=["Github Event Monitor"])
async def events_count(
    offset: int = Query(
        10,
        description="The offset determines how much time we want to look back. " \
        "i.e., an offset of 10 means we count only the events which have been created in the last 10 minutes.",
    ),
    store: RedisMetricsStore = Depends(get_store),
) -> EventCounts:
    """Return the total number of events grouped by the event type in given offset."""
    counts = store.get_event_counts_by_type(offset)
    return EventCounts(offset_minutes=offset, counts=counts)


@router.get("/tracked-repos", tags=["Debug"])
async def tracked_repos(store: RedisMetricsStore = Depends(get_store)) -> TrackedRepos:
    """Return list of repositories that have PR data tracked."""
    return TrackedRepos(repositories=store.get_tracked_repos())


@router.get("/status", tags=["Debug"])
async def status(
    store: RedisMetricsStore = Depends(get_store),
    min_pr_count: int = Query(
        2,
        description="Minimum number of pull requests for a repository to be included in the status.",
    ),
) -> Status:
    """Return the status of the Redis storage including counts and stored data."""
    return store.get_status(min_pr_count=min_pr_count)


# Only for debug, does not work when main loop is running
# @router.get("/wanted_events", tags=["Debug"])
# async def wanted_events(github_client: GitHubClient = Depends(get_github_client)) -> CategorizedEvents:
#     """Fetch and return GitHub WatchEvent, PullRequestEvent and IssuesEvent."""
#     return await github_client.get_events()
