"""Unit tests for run_github_streamer."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from github_events.github import GitHubClient
from github_events.main import run_github_streamer
from github_events.models import (
    CategorizedEvents,
    IssuesEvent,
    PullRequestEvent,
    WatchEvent,
)
from github_events.store import RedisMetricsStore


class TestRunGitHubStreamer:
    """Tests for the run_github_streamer background task."""

    @pytest.mark.asyncio
    async def test_processes_pull_request_events(self):
        """Verify PR events are stored in the metrics store."""
        mock_store = MagicMock(spec=RedisMetricsStore)
        mock_store.add_pull_request = MagicMock()
        mock_store.add_event = MagicMock()

        mock_github_client = MagicMock(spec=GitHubClient)
        mock_github_client.poll_interval = 60

        pr_event = PullRequestEvent(
            id="123",
            type="PullRequestEvent",
            actor={"id": 1, "login": "user"},
            repo={"id": 1, "name": "owner/repo"},
            created_at=datetime(2026, 3, 14, 10, 0, 0),
            payload={
                "action": "opened",
                "number": 1,
                "pull_request": {"id": 1, "number": 1},
            },
        )

        mock_github_client.get_events = AsyncMock(return_value=CategorizedEvents(
            pull_request_events=[pr_event],
            watch_events=[],
            issues_events=[],
        ))

        shutdown_event = asyncio.Event()
        call_count = 0

        async def wait_with_exit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                shutdown_event.set()
            # First call returns after small delay to allow processing
            await asyncio.sleep(0.01)

        with patch("asyncio.wait_for", side_effect=wait_with_exit):
            await run_github_streamer(mock_github_client, mock_store, shutdown_event)

        mock_store.add_pull_request.assert_called_once_with("owner/repo", pr_event.created_at)
        mock_store.add_event.assert_called_once_with("PullRequestEvent", pr_event.created_at)

    @pytest.mark.asyncio
    async def test_processes_watch_events(self):
        """Verify Watch events are stored in the metrics store."""
        mock_store = MagicMock(spec=RedisMetricsStore)
        mock_store.add_pull_request = MagicMock()
        mock_store.add_event = MagicMock()

        mock_github_client = MagicMock(spec=GitHubClient)
        mock_github_client.poll_interval = 60

        watch_event = WatchEvent(
            id="456",
            type="WatchEvent",
            actor={"id": 1, "login": "user"},
            repo={"id": 1, "name": "octocat/Hello-World"},
            created_at=datetime(2026, 3, 14, 10, 0, 0),
            payload={"action": "started"},
        )

        mock_github_client.get_events = AsyncMock(return_value=CategorizedEvents(
            pull_request_events=[],
            watch_events=[watch_event],
            issues_events=[],
        ))

        shutdown_event = asyncio.Event()
        call_count = 0

        async def wait_with_exit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                shutdown_event.set()
            await asyncio.sleep(0.01)

        with patch("asyncio.wait_for", side_effect=wait_with_exit):
            await run_github_streamer(mock_github_client, mock_store, shutdown_event)

        mock_store.add_event.assert_called_once_with("WatchEvent", watch_event.created_at)

    @pytest.mark.asyncio
    async def test_processes_issues_events(self):
        """Verify Issues events are stored in the metrics store."""
        mock_store = MagicMock(spec=RedisMetricsStore)
        mock_store.add_pull_request = MagicMock()
        mock_store.add_event = MagicMock()

        mock_github_client = MagicMock(spec=GitHubClient)
        mock_github_client.poll_interval = 60

        issues_event = IssuesEvent(
            id="789",
            type="IssuesEvent",
            actor={"id": 1, "login": "user"},
            repo={"id": 1, "name": "owner/repo"},
            created_at=datetime(2026, 3, 14, 10, 0, 0),
            payload={"action": "opened", "issue": {"id": 1, "number": 1}},
        )

        mock_github_client.get_events = AsyncMock(return_value=CategorizedEvents(
            pull_request_events=[],
            watch_events=[],
            issues_events=[issues_event],
        ))

        shutdown_event = asyncio.Event()
        call_count = 0

        async def wait_with_exit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                shutdown_event.set()
            await asyncio.sleep(0.01)

        with patch("asyncio.wait_for", side_effect=wait_with_exit):
            await run_github_streamer(mock_github_client, mock_store, shutdown_event)

        mock_store.add_event.assert_called_once_with("IssuesEvent", issues_event.created_at)

    @pytest.mark.asyncio
    async def test_processes_mixed_events(self):
        """Verify all event types are processed together."""
        mock_store = MagicMock(spec=RedisMetricsStore)
        mock_store.add_pull_request = MagicMock()
        mock_store.add_event = MagicMock()

        mock_github_client = MagicMock(spec=GitHubClient)
        mock_github_client.poll_interval = 60

        pr_event = PullRequestEvent(
            id="123",
            type="PullRequestEvent",
            actor={"id": 1, "login": "user"},
            repo={"id": 1, "name": "owner/repo"},
            created_at=datetime(2026, 3, 14, 10, 0, 0),
            payload={
                "action": "opened",
                "number": 1,
                "pull_request": {"id": 1, "number": 1},
            },
        )
        watch_event = WatchEvent(
            id="456",
            type="WatchEvent",
            actor={"id": 2, "login": "user2"},
            repo={"id": 2, "name": "other/repo"},
            created_at=datetime(2026, 3, 14, 10, 1, 0),
            payload={"action": "started"},
        )
        issues_event = IssuesEvent(
            id="789",
            type="IssuesEvent",
            actor={"id": 3, "login": "user3"},
            repo={"id": 3, "name": "another/repo"},
            created_at=datetime(2026, 3, 14, 10, 2, 0),
            payload={"action": "opened", "issue": {"id": 3, "number": 1}},
        )

        mock_github_client.get_events = AsyncMock(return_value=CategorizedEvents(
            pull_request_events=[pr_event],
            watch_events=[watch_event],
            issues_events=[issues_event],
        ))

        shutdown_event = asyncio.Event()
        call_count = 0

        async def wait_with_exit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                shutdown_event.set()
            await asyncio.sleep(0.01)

        with patch("asyncio.wait_for", side_effect=wait_with_exit):
            await run_github_streamer(mock_github_client, mock_store, shutdown_event)

        # Should call add_pull_request and add_event for PR, plus add_event for watch and issues
        assert mock_store.add_pull_request.call_count == 1
        assert mock_store.add_event.call_count == 3  # 1 PR + 1 Watch + 1 Issues

    @pytest.mark.asyncio
    async def test_handles_empty_events(self):
        """Verify empty events don't cause errors."""
        mock_store = MagicMock(spec=RedisMetricsStore)
        mock_store.add_pull_request = MagicMock()
        mock_store.add_event = MagicMock()

        mock_github_client = MagicMock(spec=GitHubClient)
        mock_github_client.poll_interval = 60
        mock_github_client.get_events = AsyncMock(return_value=CategorizedEvents())

        shutdown_event = asyncio.Event()
        call_count = 0

        async def wait_with_exit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                shutdown_event.set()
            await asyncio.sleep(0.01)

        with patch("asyncio.wait_for", side_effect=wait_with_exit):
            await run_github_streamer(mock_github_client, mock_store, shutdown_event)

        mock_store.add_pull_request.assert_not_called()
        mock_store.add_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_github_api_errors(self):
        """Verify API errors don't crash the streamer."""
        mock_store = MagicMock(spec=RedisMetricsStore)
        mock_store.add_pull_request = MagicMock()
        mock_store.add_event = MagicMock()

        mock_github_client = MagicMock(spec=GitHubClient)
        mock_github_client.poll_interval = 60
        mock_github_client.get_events = AsyncMock(side_effect=Exception("Connection failed"))

        shutdown_event = asyncio.Event()
        call_count = 0

        async def wait_with_exit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                shutdown_event.set()
            await asyncio.sleep(0.01)

        # Should not raise
        with patch("asyncio.wait_for", side_effect=wait_with_exit):
            await run_github_streamer(mock_github_client, mock_store, shutdown_event)

        # Store should not have been called since the fetch failed
        mock_store.add_pull_request.assert_not_called()
        mock_store.add_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_logs_processed_events(self, caplog):
        """Verify events are logged when processed."""
        import logging

        mock_store = MagicMock(spec=RedisMetricsStore)
        mock_store.add_pull_request = MagicMock()
        mock_store.add_event = MagicMock()

        mock_github_client = MagicMock(spec=GitHubClient)
        mock_github_client.poll_interval = 60

        pr_event = PullRequestEvent(
            id="123",
            type="PullRequestEvent",
            actor={"id": 1, "login": "user"},
            repo={"id": 1, "name": "owner/repo"},
            created_at=datetime(2026, 3, 14, 10, 0, 0),
            payload={
                "action": "opened",
                "number": 1,
                "pull_request": {"id": 1, "number": 1},
            },
        )

        mock_github_client.get_events = AsyncMock(return_value=CategorizedEvents(
            pull_request_events=[pr_event],
            watch_events=[],
            issues_events=[],
        ))

        shutdown_event = asyncio.Event()
        call_count = 0

        async def wait_with_exit(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                shutdown_event.set()
            await asyncio.sleep(0.01)

        with caplog.at_level(logging.INFO):
            with patch("asyncio.wait_for", side_effect=wait_with_exit):
                await run_github_streamer(mock_github_client, mock_store, shutdown_event)

        assert "Processed 1 events from GitHub" in caplog.text