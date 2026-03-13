import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from pydantic_core import TzInfo

from github_events.github import GitHubClient
from github_events.models import CategorizedEvents

# --- Constants & Fixtures ---

EXPECTED = {
    "watch_events": [
        {
            "id": "12345",
            "type": "WatchEvent",
            "actor": {"id": 1, "login": "octocat"},
            "repo": {"id": 3, "name": "octocat/Hello-World"},
            "created_at": datetime(2011, 9, 6, 17, 26, 27, tzinfo=TzInfo(0)),
            "payload": {"action": "started"},
        }
    ],
    "pull_request_events": [
        {
            "id": "7386628257",
            "type": "PullRequestEvent",
            "actor": {"id": 43880903, "login": "transifex-integration[bot]"},
            "repo": {"id": 2907031, "name": "Cockatrice/Cockatrice"},
            "created_at": datetime(2026, 3, 13, 20, 22, 48, tzinfo=TzInfo(0)),
            "payload": {
                "action": "merged",
                "number": 6692,
                "pull_request": {"id": 3395005953, "number": 6692},
            },
        }
    ],
    "issues_events": [
        {
            "id": "7386628203",
            "type": "IssuesEvent",
            "actor": {"id": 258433366, "login": "LinChuang2008"},
            "repo": {"id": 1160472062, "name": "LinChuang2008/vigilops"},
            "created_at": datetime(2026, 3, 13, 20, 22, 49, tzinfo=TzInfo(0)),
            "payload": {"action": "opened", "issue": {"id": 4073242583, "number": 18}},
        }
    ],
}

@pytest.fixture
def events_data() -> list:
    """Load events data from the JSON file."""
    events_path = Path(__file__).parent / "mocks" / "events.json"
    with open(events_path) as f:
        return json.load(f)

# --- Test Suite ---

class TestGitHubClient:
    """Tests for GitHubClient parsing, cooldowns, and ETag handling."""

    @pytest.mark.asyncio
    async def test_get_events_parsing(self, events_data: list):
        """Your original test: verify JSON is correctly parsed into models."""
        def handler(request: httpx.Request):
            return httpx.Response(200, json=events_data)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            github_client = GitHubClient(client)
            events = await github_client.get_events()

            assert isinstance(events, CategorizedEvents)
            assert events.model_dump() == EXPECTED

    @pytest.mark.asyncio
    async def test_cooldown_returns_empty_on_rapid_calls(self, events_data: list):
        """Verify that calling the API before cooldown finishes returns empty data 
        even if data exists on the server.
        """
        def handler(request):
            return httpx.Response(200, json=events_data)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            github_client = GitHubClient(client)

            # First call succeeds and returns the events_data
            first_fetch = await github_client.get_events()
            assert len(first_fetch.watch_events) > 0 # Confirm we actually got data
            
            # Second call immediate should return empty BECAUSE of cooldown
            # even though the handler is still providing the json=events_data
            second_fetch = await github_client.get_events()
            assert isinstance(second_fetch, CategorizedEvents)
            assert not second_fetch.watch_events
            assert not second_fetch.pull_request_events
            assert not second_fetch.issues_events

    @pytest.mark.asyncio
    async def test_etag_flow_and_304_handling(self, events_data: list):
        """Verify ETag is stored and sent back, and 304 returns empty data."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(200, json=events_data, headers={"ETag": "hash123"})
            
            # Verify the client sent the ETag back in the second request
            assert request.headers["If-None-Match"] == "hash123"
            return httpx.Response(304)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            github_client = GitHubClient(client)

            # Step 1: Populate the ETag
            await github_client.get_events()

            # Step 2: Fast-forward time to bypass the cooldown
            with patch("time.monotonic", return_value=time.monotonic() + 100):
                events = await github_client.get_events()
                # Should be empty because 304 means "no change"
                assert isinstance(events, CategorizedEvents)
                assert len(events.watch_events) == 0

    @pytest.mark.asyncio
    async def test_dynamic_interval_update(self):
        """Verify X-Poll-Interval header updates the client's internal state."""
        def handler(request):
            return httpx.Response(200, json=[], headers={"X-Poll-Interval": "120"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            github_client = GitHubClient(client)
            await github_client.get_events()
            
            assert github_client.poll_interval == 120

    @pytest.mark.asyncio
    async def test_successful_fetch_after_cooldown(self):
        """Verify the client can fetch again once the cooldown period passes."""
        # Simple mock event to distinguish from an empty return
        mock_data = [{"type": "WatchEvent", "id": "1", "created_at": "2026-03-13T20:22:48Z", 
                      "actor": {"id": 1, "login": "a"}, "repo": {"id": 1, "name": "b"}, 
                      "payload": {"action": "started"}}]

        def handler(request):
            return httpx.Response(200, json=mock_data)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            github_client = GitHubClient(client)
            
            # Call 1: Sets the initial timestamp
            await github_client.get_events()

            # Call 2: Fast-forward time by 61 seconds (beyond default 60s cooldown)
            with patch("time.monotonic", return_value=time.monotonic() + 61):
                events = await github_client.get_events()
                # Should have parsed the event because cooldown is over
                assert len(events.watch_events) == 1