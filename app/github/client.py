"""GitHub API client and webhook handling."""

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx
from github import Github, GithubIntegration
from github.PullRequest import PullRequest as GH_PullRequest
from github.Repository import Repository as GH_Repository

from app.config import get_settings
from app.schemas import (
    GitCommit,
    GitFileChange,
    GitRepository,
    GitUser,
    Provider,
    PullRequest,
    WebhookPayload,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class GitHubClient:
    """GitHub API client with App and PAT authentication support."""

    def __init__(self) -> None:
        self._client: Github | None = None
        self._integration: GithubIntegration | None = None

    def _get_client(self, installation_id: int | None = None) -> Github:
        """Get authenticated GitHub client."""
        if installation_id and settings.github_app_id and settings.github_app_private_key:
            if not self._integration:
                self._integration = GithubIntegration(
                    settings.github_app_id,
                    settings.github_app_private_key.get_secret_value(),
                )
            token = self._integration.get_access_token(installation_id).token
            return Github(token)
        elif settings.github_token:
            if not self._client:
                self._client = Github(settings.github_token.get_secret_value())
            return self._client
        raise ValueError("No GitHub authentication configured")

    async def get_pull_request(
        self, owner: str, repo: str, pr_number: int, installation_id: int | None = None
    ) -> PullRequest:
        """Fetch complete PR with file changes."""
        gh = self._get_client(installation_id)
        gh_repo: GH_Repository = gh.get_repo(f"{owner}/{repo}")
        gh_pr: GH_PullRequest = gh_repo.get_pull(pr_number)

        # Get file changes
        files = []
        for f in gh_pr.get_files():
            files.append(
                GitFileChange(
                    filename=f.filename,
                    status=f.status,
                    additions=f.additions,
                    deletions=f.deletions,
                    changes=f.changes,
                    patch=f.patch,
                    previous_filename=f.previous_filename,
                    raw_url=f.raw_url,
                    contents_url=f.contents_url,
                )
            )

        return PullRequest(
            id=gh_pr.id,
            number=gh_pr.number,
            title=gh_pr.title,
            body=gh_pr.body,
            state=gh_pr.state,
            draft=gh_pr.draft,
            head=GitCommit(
                sha=gh_pr.head.sha,
                message=gh_pr.head.commit.message if gh_pr.head.commit else "",
                author=GitUser(
                    login=gh_pr.head.user.login if gh_pr.head.user else "unknown",
                    id=gh_pr.head.user.id if gh_pr.head.user else 0,
                ),
                committer=GitUser(
                    login=gh_pr.head.user.login if gh_pr.head.user else "unknown",
                    id=gh_pr.head.user.id if gh_pr.head.user else 0,
                ),
                url=gh_pr.head.repo.html_url if gh_pr.head.repo else "",
            ),
            base=GitCommit(
                sha=gh_pr.base.sha,
                message=gh_pr.base.commit.message if gh_pr.base.commit else "",
                author=GitUser(
                    login=gh_pr.base.user.login if gh_pr.base.user else "unknown",
                    id=gh_pr.base.user.id if gh_pr.base.user else 0,
                ),
                committer=GitUser(
                    login=gh_pr.base.user.login if gh_pr.base.user else "unknown",
                    id=gh_pr.base.user.id if gh_pr.base.user.id else 0,
                ),
                url=gh_pr.base.repo.html_url if gh_pr.base.repo else "",
            ),
            user=GitUser(
                login=gh_pr.user.login,
                id=gh_pr.user.id,
                avatar_url=gh_pr.user.avatar_url,
                html_url=gh_pr.user.html_url,
            ),
            html_url=gh_pr.html_url,
            diff_url=gh_pr.diff_url,
            patch_url=gh_pr.patch_url,
            created_at=gh_pr.created_at,
            updated_at=gh_pr.updated_at,
            merged_at=gh_pr.merged_at,
            files=files,
            labels=[label.name for label in gh_pr.get_labels()],
        )

    async def get_repository(
        self, owner: str, repo: str, installation_id: int | None = None
    ) -> GitRepository:
        """Fetch repository information."""
        gh = self._get_client(installation_id)
        gh_repo: GH_Repository = gh.get_repo(f"{owner}/{repo}")
        return GitRepository(
            id=gh_repo.id,
            name=gh_repo.name,
            full_name=gh_repo.full_name,
            owner=GitUser(
                login=gh_repo.owner.login,
                id=gh_repo.owner.id,
                avatar_url=gh_repo.owner.avatar_url,
                html_url=gh_repo.owner.html_url,
            ),
            html_url=gh_repo.html_url,
            clone_url=gh_repo.clone_url,
            default_branch=gh_repo.default_branch,
            private=gh_repo.private,
        )

    async def post_review_comment(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        comments: list[dict],
        installation_id: int | None = None,
    ) -> list[dict]:
        """Post review comments to PR."""
        gh = self._get_client(installation_id)
        gh_repo: GH_Repository = gh.get_repo(f"{owner}/{repo}")
        gh_pr: GH_PullRequest = gh_repo.get_pull(pr_number)

        results = []
        for comment in comments:
            try:
                if comment.get("path") and comment.get("line"):
                    # Inline comment
                    review_comment = gh_pr.create_review_comment(
                        body=comment["body"],
                        commit=gh_pr.head.sha,
                        path=comment["path"],
                        line=comment["line"],
                        side=comment.get("side", "RIGHT"),
                    )
                else:
                    # General comment
                    review_comment = gh_pr.create_issue_comment(comment["body"])
                results.append({"success": True, "id": review_comment.id, "url": review_comment.html_url})
            except Exception as e:
                logger.error("Failed to post comment: %s", e)
                results.append({"success": False, "error": str(e)})
        return results

    async def create_review_summary(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
        installation_id: int | None = None,
    ) -> dict:
        """Create a review with summary."""
        gh = self._get_client(installation_id)
        gh_repo: GH_Repository = gh.get_repo(f"{owner}/{repo}")
        gh_pr: GH_PullRequest = gh_repo.get_pull(pr_number)
        review = gh_pr.create_review(body=body, event=event)
        return {"id": review.id, "url": review.html_url, "state": review.state}

    async def get_file_content(
        self, owner: str, repo: str, path: str, ref: str, installation_id: int | None = None
    ) -> str | None:
        """Get file content at specific ref."""
        try:
            gh = self._get_client(installation_id)
            gh_repo: GH_Repository = gh.get_repo(f"{owner}/{repo}")
            content = gh_repo.get_contents(path, ref=ref)
            if isinstance(content, list):
                return None
            return content.decoded_content.decode("utf-8")
        except Exception:
            return None


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature."""
    if not secret:
        return True  # Skip verification if no secret configured
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


async def parse_webhook_payload(
    payload: dict[str, Any], provider: Provider = Provider.GITHUB
) -> WebhookPayload:
    """Parse and normalize webhook payload."""
    if provider == Provider.GITHUB:
        return _parse_github_webhook(payload)
    raise NotImplementedError(f"Provider {provider} not yet implemented")


def _parse_github_webhook(payload: dict[str, Any]) -> WebhookPayload:
    """Parse GitHub webhook payload."""
    action = payload.get("action", "")
    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})
    sender_data = payload.get("sender", {})
    installation_data = payload.get("installation", {})

    # Build repository
    owner_data = repo_data.get("owner", {})
    repository = GitRepository(
        id=repo_data.get("id", 0),
        name=repo_data.get("name", ""),
        full_name=repo_data.get("full_name", ""),
        owner=GitUser(
            login=owner_data.get("login", ""),
            id=owner_data.get("id", 0),
            avatar_url=owner_data.get("avatar_url"),
            html_url=owner_data.get("html_url"),
        ),
        html_url=repo_data.get("html_url", ""),
        clone_url=repo_data.get("clone_url", ""),
        default_branch=repo_data.get("default_branch", "main"),
        private=repo_data.get("private", False),
    )

    sender = GitUser(
        login=sender_data.get("login", ""),
        id=sender_data.get("id", 0),
        avatar_url=sender_data.get("avatar_url"),
        html_url=sender_data.get("html_url"),
    )

    pull_request = None
    if pr_data:
        head_data = pr_data.get("head", {})
        base_data = pr_data.get("base", {})
        user_data = pr_data.get("user", {})

        pull_request = PullRequest(
            id=pr_data.get("id", 0),
            number=pr_data.get("number", 0),
            title=pr_data.get("title", ""),
            body=pr_data.get("body"),
            state=pr_data.get("state", "open"),
            draft=pr_data.get("draft", False),
            head=GitCommit(
                sha=head_data.get("sha", ""),
                message=head_data.get("commit", {}).get("message", ""),
                author=GitUser(
                    login=head_data.get("user", {}).get("login", "unknown"),
                    id=head_data.get("user", {}).get("id", 0),
                ),
                committer=GitUser(
                    login=head_data.get("user", {}).get("login", "unknown"),
                    id=head_data.get("user", {}).get("id", 0),
                ),
                url=head_data.get("repo", {}).get("html_url", ""),
            ),
            base=GitCommit(
                sha=base_data.get("sha", ""),
                message=base_data.get("commit", {}).get("message", ""),
                author=GitUser(
                    login=base_data.get("user", {}).get("login", "unknown"),
                    id=base_data.get("user", {}).get("id", 0),
                ),
                committer=GitUser(
                    login=base_data.get("user", {}).get("login", "unknown"),
                    id=base_data.get("user", {}).get("id", 0),
                ),
                url=base_data.get("repo", {}).get("html_url", ""),
            ),
            user=GitUser(
                login=user_data.get("login", ""),
                id=user_data.get("id", 0),
                avatar_url=user_data.get("avatar_url"),
                html_url=user_data.get("html_url"),
            ),
            html_url=pr_data.get("html_url", ""),
            diff_url=pr_data.get("diff_url", ""),
            patch_url=pr_data.get("patch_url", ""),
            created_at=pr_data.get("created_at"),
            updated_at=pr_data.get("updated_at"),
            merged_at=pr_data.get("merged_at"),
            files=[],  # Will be fetched separately
            labels=[label.get("name", "") for label in pr_data.get("labels", [])],
        )

    return WebhookPayload(
        provider=Provider.GITHUB,
        action=action,
        pull_request=pull_request,
        repository=repository,
        sender=sender,
        installation_id=installation_data.get("id"),
    )