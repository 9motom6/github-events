import time
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
    """A client for interacting with the GitHub API.
    
    Respects rate limits, handles ETags for 304 responses, and enforces a cooldown interval.
    """

    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._last_etag = None
        self._poll_interval = 60  # Default GitHub interval (seconds)
        self._last_call_time = 0   # Monotonic timestamp of last request
    
    @property
    def poll_interval(self) -> int:
        """The current required wait time between requests."""
        return self._poll_interval
    
    async def aclose(self):
        """Close the httpx client."""
        await self._client.aclose()

    async def get_events(self) -> CategorizedEvents:
        """Fetch and parse GitHub events.
        
        If called before the poll_interval has elapsed, or if GitHub
        returns a 304 Not Modified, it returns an empty CategorizedEvents
        object to prevent double-counting metrics.
        """
        if not self._is_cooldown_finished():
            return CategorizedEvents()
        try:
            response = await self._fetch_raw_events()
            self._update_metadata(response)
            return self._handle_response(response)
        except Exception:
            logging.exception("GitHub event fetch failed unexpectedly")
            raise
    
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
    
    def _is_cooldown_finished(self) -> bool:
        """Checks if enough time has passed since the last call.
        
        Uses Monotonic guaranteed to never move backward and to move at a constant rate.
        It doesn't care about time zones, leap seconds, or what year it is.
        It only cares about how much "real-time" has passed since the last measurement.
        """
        elapsed = time.monotonic() - self._last_call_time
        if elapsed < self._poll_interval:
            logging.info(f"Cooldown active: {self._poll_interval - elapsed:.1f}s left.")
            return False
        return True
    
    async def _fetch_raw_events(self) -> httpx.Response:
        """Executes the HTTP GET request."""
        url = "https://api.github.com/events?per_page=100"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if self._last_etag:
            headers["If-None-Match"] = self._last_etag

        self._last_call_time = time.monotonic()
        return await self._client.get(url, headers=headers)

    def _update_metadata(self, response: httpx.Response) -> None:
        """Updates interval and ETag from response headers."""
        new_interval = response.headers.get("X-Poll-Interval")
        if new_interval:
            self._poll_interval = int(new_interval)
        
        if response.status_code == 200:
            self._last_etag = response.headers.get("ETag")

    def _handle_response(self, response: httpx.Response) -> CategorizedEvents:
        """Decides whether to parse JSON or return empty on 304."""
        if response.status_code == 304:
            logging.info("GitHub returned 304: No new events.")
            return CategorizedEvents()

        response.raise_for_status()
        return self.parse_events(response.json())