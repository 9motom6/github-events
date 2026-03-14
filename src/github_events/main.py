"""FastAPI application for GitHub Event Monitor."""

import asyncio
import logging

import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI

from github_events.github import GitHubClient
from github_events.routes import router
from github_events.store import RedisMetricsStore
from github_events.worker import run_github_streamer


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

app.include_router(router)