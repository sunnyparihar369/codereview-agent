"""GitHub webhook payload models (for type hints and validation)."""

from typing import Any
from pydantic import BaseModel


class GitHubUser(BaseModel):
    login: str
    id: int
    avatar_url: str | None = None
    html_url: str | None = None


class GitHubRepo(BaseModel):
    id: int
    name: str
    full_name: str
    owner: GitHubUser
    html_url: str
    clone_url: str
    default_branch: str
    private: bool


class GitHubCommit(BaseModel):
    sha: str
    message: str
    author: GitHubUser
    committer: GitHubUser
    url: str


class GitHubFile(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: str | None = None
    previous_filename: str | None = None
    raw_url: str | None = None
    contents_url: str | None = None


class GitHubPullRequest(BaseModel):
    id: int
    number: int
    title: str
    body: str | None = None
    state: str
    draft: bool
    head: GitHubCommit
    base: GitHubCommit
    user: GitHubUser
    html_url: str
    diff_url: str
    patch_url: str
    created_at: str
    updated_at: str
    merged_at: str | None = None
    files: list[GitHubFile] = []
    labels: list[dict[str, Any]] = []


class GitHubWebhookPayload(BaseModel):
    action: str
    pull_request: GitHubPullRequest | None = None
    repository: GitHubRepo
    sender: GitHubUser
    installation: dict[str, Any] | None = None