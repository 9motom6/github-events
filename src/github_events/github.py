import logging

import httpx
from pydantic import ValidationError

from github_events.models import (
    CategorizedEvents,
    IssuesEvent,
    PullRequestEvent,
    WatchEvent,
)


class GitHubClient:
    """A client for interacting with the GitHub API."""

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def aclose(self):
        """Close the httpx client."""
        await self._client.aclose()

    async def get_events(self) -> CategorizedEvents:
        """Fetch and parse GitHub events."""
        url = "https://api.github.com/events?per_page=100"
        headers = {"Accept": "application/vnd.github+json"}
        response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        events_data = response.json()
        logging.info("Fetched events.", extra={"events": events_data})

        categorized_events = self.parse_events(events_data)
        
        total_events = (
            len(categorized_events.watch_events)
            + len(categorized_events.pull_request_events)
            + len(categorized_events.issues_events)
        )
        logging.info(f"Fetched {total_events} events.")
        return categorized_events
    
    def parse_events(self, events_data: list[dict]) -> CategorizedEvents:
        categorized_events = CategorizedEvents()
        for event_data in events_data:
            try:
                event_type = event_data.get("type")
                if event_type == "WatchEvent":
                    categorized_events.watch_events.append(
                        WatchEvent.model_validate(event_data)
                    )
                elif event_type == "PullRequestEvent":
                    categorized_events.pull_request_events.append(
                        PullRequestEvent.model_validate(event_data)
                    )
                elif event_type == "IssuesEvent":
                    categorized_events.issues_events.append(
                        IssuesEvent.model_validate(event_data)
                    )
            except ValidationError as e:
                logging.warning(f"Failed to parse event: {e}")
        return categorized_events