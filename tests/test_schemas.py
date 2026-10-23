"""Tests for Pydantic schemas."""

import pytest
from app.schemas import (
    AgentName,
    Finding,
    FindingCategory,
    PullRequest,
    ReviewResult,
    ReviewStatus,
    Severity,
    WebhookPayload,
)


def test_finding_creation():
    """Test Finding model creation with all fields."""
    finding = Finding(
        id="abc123",
        agent=AgentName.SECURITY,
        category=FindingCategory.SECURITY,
        severity=Severity.HIGH,
        title="SQL Injection",
        description="User input directly concatenated into query",
        filename="app/db.py",
        line_start=42,
        line_end=42,
        code_snippet='query = f"SELECT * FROM users WHERE id = {user_id}"',
        suggestion='query = "SELECT * FROM users WHERE id = %s"',
        rule_id="CWE-89",
        references=["https://cwe.mitre.org/data/definitions/89.html"],
        confidence=0.95,
    )
    assert finding.id == "abc123"
    assert finding.agent == AgentName.SECURITY
    assert finding.severity == Severity.HIGH
    assert finding.confidence == 0.95


def test_finding_confidence_validation():
    """Test confidence must be 0-1."""
    with pytest.raises(ValueError):
        Finding(
            id="test",
            agent=AgentName.SECURITY,
            category=FindingCategory.SECURITY,
            severity=Severity.INFO,
            title="Test",
            description="Test",
            filename="test.py",
            confidence=1.5,  # Invalid
        )

    with pytest.raises(ValueError):
        Finding(
            id="test",
            agent=AgentName.SECURITY,
            category=FindingCategory.SECURITY,
            severity=Severity.INFO,
            title="Test",
            description="Test",
            filename="test.py",
            confidence=-0.1,  # Invalid
        )


def test_review_result_stats():
    """Test ReviewResult stats aggregation."""
    findings = [
        Finding(
            id="1",
            agent=AgentName.SECURITY,
            category=FindingCategory.SECURITY,
            severity=Severity.CRITICAL,
            title="Crit",
            description="Desc",
            filename="a.py",
        ),
        Finding(
            id="2",
            agent=AgentName.PERFORMANCE,
            category=FindingCategory.PERFORMANCE,
            severity=Severity.HIGH,
            title="High",
            description="Desc",
            filename="b.py",
        ),
        Finding(
            id="3",
            agent=AgentName.STYLE,
            category=FindingCategory.STYLE,
            severity=Severity.LOW,
            title="Low",
            description="Desc",
            filename="a.py",
        ),
    ]

    result = ReviewResult(
        pr_id="github:owner/repo#123",
        status=ReviewStatus.COMPLETED,
        all_findings=findings,
        started_at="2024-01-01T00:00:00",
    )

    # Stats should be computed by aggregator, but verify structure
    assert len(result.all_findings) == 3
    assert result.status == ReviewStatus.COMPLETED


def test_pull_request_schema():
    """Test PullRequest model."""
    pr = PullRequest(
        id=123,
        number=456,
        title="Add feature",
        body="Description",
        state="open",
        draft=False,
        head={
            "sha": "abc123",
            "message": "Initial commit",
            "author": {"login": "user", "id": 1},
            "committer": {"login": "user", "id": 1},
            "url": "https://github.com/owner/repo",
        },
        base={
            "sha": "def456",
            "message": "Base commit",
            "author": {"login": "user", "id": 1},
            "committer": {"login": "user", "id": 1},
            "url": "https://github.com/owner/repo",
        },
        user={"login": "user", "id": 1},
        html_url="https://github.com/owner/repo/pull/456",
        diff_url="https://github.com/owner/repo/pull/456.diff",
        patch_url="https://github.com/owner/repo/pull/456.patch",
        created_at="2024-01-01T00:00:00",
        updated_at="2024-01-01T00:00:00",
    )
    assert pr.number == 456
    assert pr.title == "Add feature"
    assert pr.state == "open"


def test_webhook_payload():
    """Test WebhookPayload parsing."""
    payload = WebhookPayload(
        provider="github",
        action="opened",
        pull_request=None,
        repository={
            "id": 1,
            "name": "repo",
            "full_name": "owner/repo",
            "owner": {"login": "owner", "id": 1},
            "html_url": "https://github.com/owner/repo",
            "clone_url": "https://github.com/owner/repo.git",
            "default_branch": "main",
            "private": False,
        },
        sender={"login": "user", "id": 1},
    )
    assert payload.provider == "github"
    assert payload.action == "opened"
    assert payload.repository.full_name == "owner/repo"