"""Background worker for streaming GitHub events."""

import asyncio
import logging
import time

from github_events.github import GitHubClient
from github_events.models import CategorizedEvents
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