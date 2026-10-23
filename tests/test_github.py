"""Tests for GitHub client and webhook handling."""

import hmac
import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from github import GithubException

from app.github.client import GitHubClient, verify_webhook_signature
from app.schemas import Provider, WebhookPayload


class TestWebhookSignature:
    """Tests for webhook signature verification."""

    def test_valid_signature(self):
        """Test valid HMAC signature."""
        secret = "test-secret"
        payload = b'{"action": "opened"}'
        signature = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        assert verify_webhook_signature(payload, signature, secret) is True

    def test_invalid_signature(self):
        """Test invalid HMAC signature."""
        secret = "test-secret"
        payload = b'{"action": "opened"}'
        signature = "sha256=invalidhash"

        assert verify_webhook_signature(payload, signature, secret) is False

    def test_no_secret_configured(self):
        """Test verification skipped when no secret."""
        payload = b'{"action": "opened"}'
        signature = "sha256=anything"

        assert verify_webhook_signature(payload, signature, "") is True


class TestGitHubClient:
    """Tests for GitHubClient."""

    @pytest.fixture
    def client(self):
        return GitHubClient()

    @pytest.fixture
    def mock_github(self):
        with patch("app.github.client.Github") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_get_pull_request_with_token(self, client, mock_github):
        """Test fetching PR with PAT authentication."""
        # Setup mocks
        mock_gh = MagicMock()
        mock_github.return_value = mock_gh

        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        mock_pr = MagicMock()
        mock_pr.id = 123
        mock_pr.number = 456
        mock_pr.title = "Test PR"
        mock_pr.body = "Description"
        mock_pr.state = "open"
        mock_pr.draft = False
        mock_pr.head.sha = "abc123"
        mock_pr.head.commit.message = "Commit msg"
        mock_pr.head.user.login = "author"
        mock_pr.head.user.id = 1
        mock_pr.head.repo.html_url = "https://github.com/owner/repo"
        mock_pr.base.sha = "def456"
        mock_pr.base.commit.message = "Base commit"
        mock_pr.base.user.login = "author"
        mock_pr.base.user.id = 1
        mock_pr.base.repo.html_url = "https://github.com/owner/repo"
        mock_pr.user.login = "author"
        mock_pr.user.id = 1
        mock_pr.user.avatar_url = "https://github.com/avatar.png"
        mock_pr.user.html_url = "https://github.com/author"
        mock_pr.html_url = "https://github.com/owner/repo/pull/456"
        mock_pr.diff_url = "https://github.com/owner/repo/pull/456.diff"
        mock_pr.patch_url = "https://github.com/owner/repo/pull/456.patch"
        mock_pr.created_at = "2024-01-01T00:00:00"
        mock_pr.updated_at = "2024-01-01T00:00:00"
        mock_pr.merged_at = None
        mock_pr.get_labels.return_value = []

        # Mock file
        mock_file = MagicMock()
        mock_file.filename = "test.py"
        mock_file.status = "modified"
        mock_file.additions = 10
        mock_file.deletions = 5
        mock_file.changes = 15
        mock_file.patch = "@@ -1,5 +1,5 @@"
        mock_file.previous_filename = None
        mock_file.raw_url = "https://github.com/owner/repo/raw/main/test.py"
        mock_file.contents_url = "https://api.github.com/repos/owner/repo/contents/test.py"
        mock_pr.get_files.return_value = [mock_file]

        mock_repo.get_pull.return_value = mock_pr

        # Test
        with patch.object(client, "_get_client", return_value=mock_gh):
            pr = await client.get_pull_request("owner", "repo", 456)

        assert pr.id == 123
        assert pr.number == 456
        assert pr.title == "Test PR"
        assert len(pr.files) == 1
        assert pr.files[0].filename == "test.py"

    @pytest.mark.asyncio
    async def test_get_pull_request_not_found(self, client, mock_github):
        """Test PR not found error."""
        mock_gh = MagicMock()
        mock_github.return_value = mock_gh
        mock_gh.get_repo.side_effect = GithubException(404, {}, {"message": "Not Found"})

        with patch.object(client, "_get_client", return_value=mock_gh):
            with pytest.raises(GithubException):
                await client.get_pull_request("owner", "repo", 999)


class TestParseWebhookPayload:
    """Tests for webhook payload parsing."""

    @pytest.mark.asyncio
    async def test_parse_github_pull_request_opened(self):
        """Test parsing PR opened webhook."""
        payload = {
            "action": "opened",
            "pull_request": {
                "id": 123,
                "number": 456,
                "title": "New Feature",
                "body": "Description",
                "state": "open",
                "draft": False,
                "head": {
                    "sha": "abc123",
                    "commit": {"message": "Add feature"},
                    "user": {"login": "author", "id": 1},
                },
                "base": {
                    "sha": "def456",
                    "commit": {"message": "Base"},
                    "user": {"login": "author", "id": 1},
                },
                "user": {"login": "author", "id": 1, "avatar_url": "", "html_url": ""},
                "html_url": "https://github.com/owner/repo/pull/456",
                "diff_url": "https://github.com/owner/repo/pull/456.diff",
                "patch_url": "https://github.com/owner/repo/pull/456.patch",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
                "merged_at": None,
                "labels": [],
            },
            "repository": {
                "id": 1,
                "name": "repo",
                "full_name": "owner/repo",
                "owner": {"login": "owner", "id": 1, "avatar_url": "", "html_url": ""},
                "html_url": "https://github.com/owner/repo",
                "clone_url": "https://github.com/owner/repo.git",
                "default_branch": "main",
                "private": False,
            },
            "sender": {"login": "author", "id": 1, "avatar_url": "", "html_url": ""},
            "installation": {"id": 789},
        }

        result = WebhookPayload.model_validate(payload)

        assert result.provider == Provider.GITHUB
        assert result.action == "opened"
        assert result.installation_id == 789
        assert result.pull_request is not None
        assert result.pull_request.number == 456
        assert result.repository.full_name == "owner/repo"

    @pytest.mark.asyncio
    async def test_parse_github_pull_request_synchronize(self):
        """Test parsing PR synchronize (push) webhook."""
        payload = {
            "action": "synchronize",
            "pull_request": {
                "id": 123,
                "number": 456,
                "title": "Updated PR",
                "body": "Updated",
                "state": "open",
                "draft": False,
                "head": {
                    "sha": "newsha",
                    "commit": {"message": "Update"},
                    "user": {"login": "author", "id": 1},
                },
                "base": {
                    "sha": "basesha",
                    "commit": {"message": "Base"},
                    "user": {"login": "author", "id": 1},
                },
                "user": {"login": "author", "id": 1},
                "html_url": "https://github.com/owner/repo/pull/456",
                "diff_url": "https://github.com/owner/repo/pull/456.diff",
                "patch_url": "https://github.com/owner/repo/pull/456.patch",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-02T00:00:00",
                "merged_at": None,
                "labels": [],
            },
            "repository": {
                "id": 1,
                "name": "repo",
                "full_name": "owner/repo",
                "owner": {"login": "owner", "id": 1},
                "html_url": "https://github.com/owner/repo",
                "clone_url": "https://github.com/owner/repo.git",
                "default_branch": "main",
                "private": False,
            },
            "sender": {"login": "author", "id": 1},
            "installation": {"id": 789},
        }

        result = WebhookPayload.model_validate(payload)

        assert result.action == "synchronize"
        assert result.pull_request.head.sha == "newsha"