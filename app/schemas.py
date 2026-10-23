"""Core Pydantic schemas for the code review system."""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal
from pydantic import BaseModel, Field, HttpUrl
from pydantic.types import SecretStr


class Provider(str, Enum):
    """Supported Git providers."""

    GITHUB = "github"
    GITLAB = "gitlab"


class ReviewStatus(str, Enum):
    """Overall review status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Severity(str, Enum):
    """Finding severity levels."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingCategory(str, Enum):
    """Categories of findings."""

    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    ARCHITECTURE = "architecture"
    TESTS = "tests"
    DOCUMENTATION = "documentation"
    BUG_RISK = "bug_risk"
    MAINTAINABILITY = "maintainability"


class AgentName(str, Enum):
    """Specialist agent identifiers."""

    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    ARCHITECTURE = "architecture"
    TESTS = "tests"
    AGGREGATOR = "aggregator"


# GitHub/GitLab Webhook Payloads


class GitUser(BaseModel):
    """Git user information."""

    login: str
    id: int
    avatar_url: HttpUrl | None = None
    html_url: HttpUrl | None = None


class GitRepository(BaseModel):
    """Repository information."""

    id: int
    name: str
    full_name: str
    owner: GitUser
    html_url: HttpUrl
    clone_url: HttpUrl
    default_branch: str
    private: bool


class GitCommit(BaseModel):
    """Commit information."""

    sha: str
    message: str
    author: GitUser
    committer: GitUser
    url: HttpUrl


class GitFileChange(BaseModel):
    """File change in a PR/MR."""

    filename: str
    status: Literal["added", "removed", "modified", "renamed", "copied"]
    additions: int
    deletions: int
    changes: int
    patch: str | None = None
    previous_filename: str | None = None
    raw_url: HttpUrl | None = None
    contents_url: HttpUrl | None = None


class PullRequest(BaseModel):
    """Pull Request / Merge Request."""

    id: int
    number: int
    title: str
    body: str | None = None
    state: Literal["open", "closed", "merged"]
    draft: bool
    head: GitCommit
    base: GitCommit
    user: GitUser
    html_url: HttpUrl
    diff_url: HttpUrl
    patch_url: HttpUrl
    created_at: datetime
    updated_at: datetime
    merged_at: datetime | None = None
    files: list[GitFileChange] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)


class WebhookPayload(BaseModel):
    """Unified webhook payload."""

    provider: Provider
    action: str
    pull_request: PullRequest | None = None
    repository: GitRepository
    sender: GitUser
    installation_id: int | None = None


# Internal Domain Models


class FileContext(BaseModel):
    """Context for a single file being reviewed."""

    filename: str
    language: str | None = None
    content_before: str | None = None
    content_after: str | None = None
    diff: str
    additions: int
    deletions: int
    line_count: int


class PRContext(BaseModel):
    """Complete context for a PR review."""

    pr_id: str  # "github:owner/repo#123"
    provider: Provider
    repository: GitRepository
    pull_request: PullRequest
    files: list[FileContext]
    linked_issues: list[str] = Field(default_factory=list)
    repo_conventions: dict[str, Any] = Field(default_factory=dict)
    previous_reviews: list[dict] = Field(default_factory=list)


class Finding(BaseModel):
    """A single review finding."""

    id: str = Field(description="Unique finding identifier")
    agent: AgentName
    category: FindingCategory
    severity: Severity
    title: str
    description: str
    filename: str
    line_start: int | None = None
    line_end: int | None = None
    code_snippet: str | None = None
    suggestion: str | None = None
    rule_id: str | None = None
    references: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Result from a specialist agent."""

    agent: AgentName
    findings: list[Finding] = Field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: int = 0
    tokens_used: int = 0
    model_used: str = ""
    errors: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    """Aggregated review result."""

    pr_id: str
    status: ReviewStatus
    agent_results: dict[AgentName, AgentResult] = Field(default_factory=dict)
    all_findings: list[Finding] = Field(default_factory=list)
    summary: str = ""
    stats: dict[str, int] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime | None = None
    total_time_ms: int = 0
    total_tokens: int = 0


class ReviewComment(BaseModel):
    """Comment to post on PR."""

    body: str
    path: str | None = None
    line: int | None = None
    side: Literal["LEFT", "RIGHT"] = "RIGHT"
    start_line: int | None = None
    start_side: Literal["LEFT", "RIGHT"] = "RIGHT"


# API Schemas


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    environment: str
    timestamp: datetime


class WebhookResponse(BaseModel):
    """Webhook processing response."""

    accepted: bool
    pr_id: str | None = None
    message: str


class ReviewRequest(BaseModel):
    """Manual review trigger request."""

    pr_url: HttpUrl
    provider: Provider = Provider.GITHUB
    force: bool = False


class ReviewResponse(BaseModel):
    """Review trigger response."""

    review_id: str
    status: ReviewStatus
    message: str