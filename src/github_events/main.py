import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from github_events.github import GitHubClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the application's lifespan."""
    logging.basicConfig(level=logging.INFO)
    app.state.github_client = GitHubClient(httpx.AsyncClient())
    yield
    # Clean up the client...
    await app.state.github_client.aclose()


app = FastAPI(
    title="GitHub Event Monitor",
    description="An API for streaming and analyzing GitHub events.",
    lifespan=lifespan,
)


@app.get("/wanted_events", tags=["Health"])
async def wanted_events():
    """Fetch and return GitHub WatchEvent, PullRequestEvent and IssuesEvent."""
    return await app.state.github_client.get_events()
