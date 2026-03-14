"""FastAPI application for GitHub Event Monitor."""

import asyncio
import logging
from contextlib import asynccontextmanager
import time

import httpx
from fastapi import Depends, FastAPI, Request

from github_events.github import GitHubClient
from github_events.models import CategorizedEvents
from github_events.responses import (
    AveragePRTime,
    EventCounts,
    Status,
    TrackedRepos,
)
from github_events.store import RedisMetricsStore


async def run_github_streamer(
    github_client: GitHubClient,
    store: RedisMetricsStore,
    shutdown_event: asyncio.Event,
):
    """Background task that streams GitHub events and stores them in the metrics store.

    This runs in a loop, fetching events and populating the store with:
    - Pull request timing data (for average PR time calculation)
    - All event data (for offset-based counting)
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting GitHub event streamer background task")
    last_cleanup = time.monotonic()

    while not shutdown_event.is_set():
        try:
            events: CategorizedEvents = await github_client.get_events()

            # Process pull request events
            for pr_event in events.pull_request_events:
                store.add_pull_request(pr_event.repo.name, pr_event.created_at)
                store.add_event("PullRequestEvent", pr_event.created_at)
                logger.debug(f"Stored PR event for {pr_event.repo.name}")

            # Process watch events
            for watch_event in events.watch_events:
                store.add_event("WatchEvent", watch_event.created_at)
                logger.debug(f"Stored Watch event for {watch_event.repo.name}")

            # Process issues events
            for issue_event in events.issues_events:
                store.add_event("IssuesEvent", issue_event.created_at)
                logger.debug(f"Stored Issues event for {issue_event.repo.name}")

            total_events = (
                len(events.pull_request_events)
                + len(events.watch_events)
                + len(events.issues_events)
            )
            if total_events > 0:
                logger.info(f"Processed {total_events} events from GitHub")
                
            if time.monotonic() - last_cleanup > 3600:
                removed = store.cleanup()
                logger.info(f"Cleaned up {removed} stale records from Redis")
                last_cleanup = time.monotonic()
                
        except Exception:
            logger.exception("Error in GitHub event streamer")

        # Wait for the poll interval before next fetch
        # Use a shorter interval for shutdown checking
        interval = min(github_client.poll_interval, 5)
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass  # Timeout is expected, loop continues

    logger.info("GitHub event streamer background task stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the application's lifespan."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    github_client = GitHubClient(httpx.AsyncClient())
    store = RedisMetricsStore()

    app.state.github_client = github_client
    app.state.store = store

    # Create shutdown event for the background task
    shutdown_event = asyncio.Event()

    # Start the background streamer task
    streamer_task = asyncio.create_task(
        run_github_streamer(github_client, store, shutdown_event)
    )

    logger.info("Application started, GitHub event streamer running")

    yield

    # Signal shutdown and wait for the streamer to finish
    logger.info("Shutting down...")
    shutdown_event.set()
    await streamer_task

    await github_client.aclose()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="GitHub Event Monitor",
    description="An API for streaming and analyzing GitHub events.",
    lifespan=lifespan,
)

def get_github_client(request: Request) -> GitHubClient:
    return request.app.state.github_client

def get_store(request: Request) -> RedisMetricsStore:
    return request.app.state.store

@app.get("/wanted_events")
async def wanted_events(github_client: GitHubClient = Depends(get_github_client)) -> CategorizedEvents:
    """Fetch and return GitHub WatchEvent, PullRequestEvent and IssuesEvent."""
    return await github_client.get_events()


@app.get("/tracked-repos")
async def tracked_repos(store: RedisMetricsStore = Depends(get_store)) -> TrackedRepos:
    """Return list of repositories that have PR data tracked."""
    return TrackedRepos(store.get_tracked_repos())


@app.get("/average-pr-time")
async def average_pr_time(repository: str, store: RedisMetricsStore = Depends(get_store)) -> AveragePRTime:
    """Calculate the average time between pull requests for a given repository."""
    avg_time = store.get_average_pr_time(repository)
    return AveragePRTime(repository=repository, average_pr_time_seconds=avg_time)


@app.get("/events-count")
async def events_count(offset: int = 10, store: RedisMetricsStore = Depends(get_store)) -> EventCounts:
    """Return the total number of events grouped by the event type for a given offset.

    The offset determines how much time we want to look back
    i.e., an offset of 10 means we count only the events which have been created in the last 10 minutes.
    """
    counts = store.get_event_counts_by_type(offset)
    return EventCounts(offset_minutes=offset, counts=counts)


@app.get("/status")
async def status(store: RedisMetricsStore = Depends(get_store)) -> Status:
    """Return the status of the Redis storage including counts and stored data."""
    return store.get_status()
