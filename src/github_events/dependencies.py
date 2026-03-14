"""FastAPI dependency functions."""

from fastapi import Request

from github_events.github import GitHubClient
from github_events.store import RedisMetricsStore


def get_github_client(request: Request) -> GitHubClient:
    return request.app.state.github_client


def get_store(request: Request) -> RedisMetricsStore:
    return request.app.state.store