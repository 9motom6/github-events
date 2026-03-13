"""FastAPI application for GitHub Event Monitor."""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from github_events.github import GitHubClient
from github_events.store import RedisMetricsStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the application's lifespan."""
    logging.basicConfig(level=logging.INFO)
    app.state.github_client = GitHubClient(httpx.AsyncClient())
    app.state.store = RedisMetricsStore()
    yield
    await app.state.github_client.aclose()


app = FastAPI(
    title="GitHub Event Monitor",
    description="An API for streaming and analyzing GitHub events.",
    lifespan=lifespan,
)


@app.get("/wanted_events")
async def wanted_events():
    """Fetch and return GitHub WatchEvent, PullRequestEvent and IssuesEvent."""
    return await app.state.github_client.get_events()


@app.get("/average-pr-time")
async def average_pr_time(repository: str):
    """Calculate the average time between pull requests for a given repository."""
    avg_time = app.state.store.get_average_pr_time(repository)
    return {"repository": repository, "average_pr_time_seconds": avg_time}


@app.get("/events-count")
async def events_count(offset: int = 10):
    """Return the total number of events grouped by the event type for a given offset.

    The offset determines how much time we want to look back
    i.e., an offset of 10 means we count only the events which have been created in the last 10 minutes.
    """
    counts = app.state.store.get_event_counts_by_type(offset)
    return {"offset_minutes": offset, "counts": counts}