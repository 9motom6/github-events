"""Unit tests for RedisMetricsStore."""

from datetime import datetime, timezone, timedelta

import fakeredis
import pytest

from github_events.store import RedisMetricsStore


@pytest.fixture
def fake_redis():
    """Create a fake Redis instance."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def store(fake_redis):
    """Create a RedisMetricsStore with fake Redis."""
    return RedisMetricsStore(redis_client=fake_redis, max_events_per_type=5)


class TestPullRequestMetrics:
    """Tests for PR time tracking."""

    def test_first_pr_returns_none(self, store):
        """First PR should return None since we need at least 2 PRs."""
        result = store.get_average_pr_time("owner/repo")
        assert result is None

    def test_single_pr_returns_none(self, store):
        """Single PR should return None."""
        store.add_pull_request("owner/repo", datetime.now(timezone.utc))
        result = store.get_average_pr_time("owner/repo")
        assert result is None

    def test_two_prs_returns_average(self, store):
        """Two PRs should return the average time between them."""
        now = datetime.now(timezone.utc)
        earlier = now - timedelta(hours=1)

        store.add_pull_request("owner/repo", earlier)
        store.add_pull_request("owner/repo", now)

        result = store.get_average_pr_time("owner/repo")
        assert result == 3600.0  # 1 hour in seconds

    def test_three_prs_returns_running_average(self, store):
        """Three PRs should return running average."""
        now = datetime.now(timezone.utc)
        t1 = now - timedelta(hours=3)
        t2 = now - timedelta(hours=2)
        t3 = now

        store.add_pull_request("owner/repo", t1)
        store.add_pull_request("owner/repo", t2)
        store.add_pull_request("owner/repo", t3)

        result = store.get_average_pr_time("owner/repo")
        # t1->t2: 1hr, t2->t3: 2hrs, running avg = (3600 + 7200) / 2 = 5400
        assert result == 5400.0

    def test_different_repos_independent(self, store):
        """Different repos should have independent PR stats."""
        now = datetime.now(timezone.utc)
        earlier = now - timedelta(hours=1)

        store.add_pull_request("owner/repo1", earlier)
        store.add_pull_request("owner/repo1", now)

        # repo2 has only one PR
        store.add_pull_request("owner/repo2", now)

        assert store.get_average_pr_time("owner/repo1") == 3600.0
        assert store.get_average_pr_time("owner/repo2") is None


class TestEventCounts:
    """Tests for event counting with time offset."""

    def test_empty_returns_empty_dict(self, store):
        """No events should return empty dict."""
        result = store.get_event_counts_by_type(10)
        assert result == {}

    def test_single_event_count(self, store):
        """Single event should be counted."""
        now = datetime.now(timezone.utc)
        store.add_event("PullRequestEvent", now)

        result = store.get_event_counts_by_type(10)
        assert result == {"PullRequestEvent": 1}

    def test_events_outside_offset_not_counted(self, store):
        """Events outside the offset should not be counted."""
        now = datetime.now(timezone.utc)
        old = now - timedelta(minutes=15)

        store.add_event("PullRequestEvent", old)  # older than 10 min
        store.add_event("PullRequestEvent", now)   # within 10 min

        result = store.get_event_counts_by_type(10)
        assert result == {"PullRequestEvent": 1}

    def test_multiple_event_types(self, store):
        """Multiple event types should be counted separately."""
        now = datetime.now(timezone.utc)

        store.add_event("PullRequestEvent", now)
        store.add_event("WatchEvent", now)
        store.add_event("WatchEvent", now)

        result = store.get_event_counts_by_type(10)
        assert result["PullRequestEvent"] == 1
        assert result["WatchEvent"] == 2

    def test_offset_filters_old_events(self, store):
        """Offset should filter events older than N minutes."""
        now = datetime.now(timezone.utc)

        store.add_event("PullRequestEvent", now)
        store.add_event("PullRequestEvent", now - timedelta(minutes=5))
        store.add_event("PullRequestEvent", now - timedelta(minutes=20))

        result = store.get_event_counts_by_type(10)
        # Only 2 events within the last 10 minutes
        assert result == {"PullRequestEvent": 2}

    def test_trim_old_events(self, store):
        """Events should be trimmed when exceeding max limit."""
        now = datetime.now(timezone.utc)

        # Add 7 events (max is 5)
        for i in range(7):
            store.add_event("PullRequestEvent", now - timedelta(minutes=i))

        result = store.get_event_counts_by_type(60)
        # Should only keep 5 newest
        assert result["PullRequestEvent"] == 5


class TestStatus:
    """Tests for get_status method."""

    def test_empty_status(self, store):
        """Empty store should return zero counts."""
        result = store.get_status()

        assert result["events"]["total"] == 0
        assert result["events"]["by_type"] == {}
        assert result["pull_requests"]["repositories_tracked"] == 0
        assert result["pull_requests"]["repositories"] == {}

    def test_status_with_events(self, store):
        """Status should reflect stored events."""
        now = datetime.now(timezone.utc)

        store.add_event("PullRequestEvent", now)
        store.add_event("WatchEvent", now)
        store.add_event("WatchEvent", now)

        result = store.get_status()

        assert result["events"]["total"] == 3
        assert result["events"]["by_type"]["PullRequestEvent"] == 1
        assert result["events"]["by_type"]["WatchEvent"] == 2
        assert result["events"]["config"]["max_per_type"] == 5

    def test_status_with_prs(self, store):
        """Status should reflect stored PR data."""
        now = datetime.now(timezone.utc)
        earlier = now - timedelta(hours=1)

        store.add_pull_request("owner/repo1", earlier)
        store.add_pull_request("owner/repo1", now)

        result = store.get_status()

        assert result["pull_requests"]["repositories_tracked"] == 1
        assert "owner/repo1" in result["pull_requests"]["repositories"]
        # count stores number of completed deltas (PRs - 1), so 2 PRs = 1 delta
        assert result["pull_requests"]["repositories"]["owner/repo1"]["count"] == 1
        assert result["pull_requests"]["repositories"]["owner/repo1"]["average_pr_time_seconds"] == 3600.0


    def test_status_with_multiple_repos(self, store):
        """Status should reflect multiple PR repositories."""
        now = datetime.now(timezone.utc)
        store.add_pull_request("owner/repo1", now - timedelta(hours=1))
        store.add_pull_request("owner/repo1", now)
        store.add_pull_request("owner/repo2", now)

        status = store.get_status()

        assert status["pull_requests"]["repositories_tracked"] == 2
        # count stores number of completed deltas (PRs - 1)
        assert status["pull_requests"]["repositories"]["owner/repo1"]["count"] == 1
        assert status["pull_requests"]["repositories"]["owner/repo1"]["average_pr_time_seconds"] == 3600.0
        # Single PR has no delta yet
        assert status["pull_requests"]["repositories"]["owner/repo2"]["count"] == 0
        assert status["pull_requests"]["repositories"]["owner/repo2"]["average_pr_time_seconds"] is None