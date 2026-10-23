"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.config import Settings


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    return Settings(
        environment="test",
        log_level="DEBUG",
        github_token="ghp_test",
        anthropic_api_key="sk-ant-test",
        default_llm_provider="anthropic",
        model_simple="claude-3-5-haiku-20241022",
        model_complex="claude-3-5-sonnet-20241022",
        langsmith_tracing=False,
        enable_learning_loop=False,
    )


@pytest.fixture
def mock_llm_models():
    """Mock LLM models for testing."""
    model_simple = AsyncMock()
    model_simple.model_name = "test-simple"
    model_simple.ainvoke = AsyncMock()

    model_complex = AsyncMock()
    model_complex.model_name = "test-complex"
    model_complex.ainvoke = AsyncMock()

    return {"simple": model_simple, "complex": model_complex}


@pytest.fixture
def sample_pr_context():
    """Sample PR context for testing."""
    from app.schemas import PRContext, PullRequest, GitRepository, GitUser, GitCommit, GitFileChange

    return PRContext(
        pr_id="github:owner/repo#123",
        provider="github",
        repository=GitRepository(
            id=1,
            name="repo",
            full_name="owner/repo",
            owner=GitUser(login="owner", id=1),
            html_url="https://github.com/owner/repo",
            clone_url="https://github.com/owner/repo.git",
            default_branch="main",
            private=False,
        ),
        pull_request=PullRequest(
            id=123,
            number=123,
            title="Test PR",
            body="Test description",
            state="open",
            draft=False,
            head=GitCommit(
                sha="abc123",
                message="Test commit",
                author=GitUser(login="author", id=1),
                committer=GitUser(login="author", id=1),
                url="https://github.com/owner/repo",
            ),
            base=GitCommit(
                sha="def456",
                message="Base commit",
                author=GitUser(login="author", id=1),
                committer=GitUser(login="author", id=1),
                url="https://github.com/owner/repo",
            ),
            user=GitUser(login="author", id=1),
            html_url="https://github.com/owner/repo/pull/123",
            diff_url="https://github.com/owner/repo/pull/123.diff",
            patch_url="https://github.com/owner/repo/pull/123.patch",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            files=[
                GitFileChange(
                    filename="test.py",
                    status="modified",
                    additions=10,
                    deletions=5,
                    changes=15,
                    patch="@@ -1,5 +1,5 @@\n-def foo():\n+def bar():",
                )
            ],
        ),
        files=[
            MagicMock(
                filename="test.py",
                language="python",
                content_before="def foo():\n    pass",
                content_after="def bar():\n    pass",
                diff="@@ -1,5 +1,5 @@\n-def foo():\n+def bar():",
                additions=10,
                deletions=5,
                line_count=15,
            )
        ],
    )


# Need to import MagicMock
from unittest.mock import MagicMock