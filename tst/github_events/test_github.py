from datetime import datetime
import json
from pathlib import Path

import httpx
from pydantic_core import TzInfo
import pytest
from github_events.github import GitHubClient
from github_events.models import CategorizedEvents


@pytest.fixture
def events_data() -> list:
    """Load events data from the JSON file."""
    events_path = Path(__file__).parent / "mocks" / "events.json"
    with open(events_path) as f:
        return json.load(f)


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


@pytest.mark.asyncio
async def test_get_events(events_data: list):
    """Test that get_events returns a list of events."""

    def handler(request: httpx.Request):
        return httpx.Response(200, json=events_data)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        github_client = GitHubClient(client)

        events = await github_client.get_events()

        assert isinstance(events, CategorizedEvents)
        assert events.model_dump() == EXPECTED
