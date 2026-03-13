import logging
from typing import List, Union

import httpx
from pydantic import ValidationError

from github_events.models import (
    IssuesEvent,
    PullRequestEvent,
    WatchEvent,
)

EventType = Union[WatchEvent, PullRequestEvent, IssuesEvent]


class GitHubClient:
    """A client for interacting with the GitHub API."""

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    async def aclose(self):
        """Close the httpx client."""
        await self._client.aclose()

    async def get_events(self) -> List[EventType]:
        """Fetch and parse GitHub events."""
        url = "https://api.github.com/events"
        response = await self._client.get(url)
        response.raise_for_status()
        events_data = response.json()

        events: List[EventType] = []
        for event_data in events_data:
            try:
                event_type = event_data.get("type")
                if event_type == "WatchEvent":
                    events.append(WatchEvent.model_validate(event_data))
                elif event_type == "PullRequestEvent":
                    events.append(PullRequestEvent.model_validate(event_data))
                elif event_type == "IssuesEvent":
                    events.append(IssuesEvent.model_validate(event_data))
            except ValidationError as e:
                logging.warning(f"Failed to parse event: {e}")
        logging.info(f"Fetched {len(events)} events.")
        return events