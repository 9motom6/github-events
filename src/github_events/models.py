"""Pydantic models for GitHub events."""

from datetime import datetime
from typing import List, Literal

from pydantic import BaseModel, Field


class Actor(BaseModel):
    """Represents the user who triggered the event."""

    id: int
    login: str


class Repo(BaseModel):
    """Represents the repository where the event occurred."""

    id: int
    name: str


class BaseEvent(BaseModel):
    """Base model for all GitHub events."""

    id: str
    type: str
    actor: Actor
    repo: Repo
    created_at: datetime

class WatchEventPayload(BaseModel):
    """Payload for a WatchEvent."""

    action: str


class WatchEvent(BaseEvent):
    """Represents a WatchEvent."""

    type: Literal["WatchEvent"]
    payload: WatchEventPayload


class PullRequest(BaseModel):
    """Represents a pull request."""

    id: int
    number: int


class PullRequestEventPayload(BaseModel):
    """Payload for a PullRequestEvent."""

    action: str
    number: int
    pull_request: PullRequest


class PullRequestEvent(BaseEvent):
    """Represents a PullRequestEvent."""

    type: Literal["PullRequestEvent"]
    payload: PullRequestEventPayload


class Issue(BaseModel):
    """Represents an issue."""

    id: int
    number: int


class IssuesEventPayload(BaseModel):
    """Payload for an IssuesEvent."""

    action: str
    issue: Issue


class IssuesEvent(BaseEvent):
    """Represents an IssuesEvent."""

    type: Literal["IssuesEvent"]
    payload: IssuesEventPayload


class CategorizedEvents(BaseModel):
    """Represents categorized GitHub events."""

    watch_events: List[WatchEvent] = []
    pull_request_events: List[PullRequestEvent] = []
    issues_events: List[IssuesEvent] = []
    