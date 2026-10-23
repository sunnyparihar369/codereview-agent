"""GitHub webhook event handlers."""

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from github import GithubException

from app.config import get_settings
from app.github.client import GitHubClient, parse_webhook_payload, verify_webhook_signature
from app.schemas import Provider, WebhookPayload, WebhookResponse
from app.main import review_queue

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/webhook", tags=["webhook"])
github_client = GitHubClient()


@router.post("/github", response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_github_delivery: str = Header(..., alias="X-GitHub-Delivery"),
    x_hub_signature_256: str = Header("", alias="X-Hub-Signature-256"),
) -> WebhookResponse:
    """Handle GitHub webhook events."""
    payload_bytes = await request.body()

    # Verify signature
    if settings.github_webhook_secret:
        if not verify_webhook_signature(
            payload_bytes, x_hub_signature_256, settings.github_webhook_secret.get_secret_value()
        ):
            logger.warning("Invalid webhook signature for delivery %s", x_github_delivery)
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.info("Received GitHub event: %s (delivery: %s)", x_github_event, x_github_delivery)

    # Parse payload
    try:
        webhook_payload: WebhookPayload = await parse_webhook_payload(payload, Provider.GITHUB)
    except Exception as e:
        logger.error("Failed to parse webhook: %s", e)
        raise HTTPException(status_code=400, detail="Invalid payload structure")

    # Handle only relevant events
    if x_github_event == "pull_request":
        return await _handle_pull_request_event(webhook_payload, x_github_event)
    elif x_github_event == "pull_request_review":
        return await _handle_review_event(webhook_payload)
    elif x_github_event == "pull_request_review_comment":
        return await _handle_review_comment_event(webhook_payload)

    return WebhookResponse(accepted=True, message=f"Ignored event: {x_github_event}")


async def _handle_pull_request_event(
    payload: WebhookPayload, event: str
) -> WebhookResponse:
    """Handle pull_request events."""
    if not payload.pull_request:
        return WebhookResponse(accepted=True, message="No PR in payload")

    pr = payload.pull_request
    action = payload.action

    # Only process relevant actions
    relevant_actions = {"opened", "reopened", "synchronize", "ready_for_review"}
    if action not in relevant_actions:
        return WebhookResponse(accepted=True, message=f"Ignored action: {action}")

    # Skip draft PRs unless ready_for_review
    if pr.draft and action != "ready_for_review":
        return WebhookResponse(accepted=True, message="Draft PR, skipping")

    # Check file count and size limits
    if len(pr.files) > settings.max_files_per_pr:
        return WebhookResponse(
            accepted=False,
            pr_id=f"github:{payload.repository.full_name}#{pr.number}",
            message=f"Too many files: {len(pr.files)} > {settings.max_files_per_pr}",
        )

    # Queue for review
    pr_id = f"github:{payload.repository.full_name}#{pr.number}"
    await review_queue.enqueue(
        pr_id=pr_id,
        provider=Provider.GITHUB,
        repository=payload.repository,
        pull_request=pr,
        installation_id=payload.installation_id,
        trigger=action,
    )

    return WebhookResponse(
        accepted=True,
        pr_id=pr_id,
        message=f"Queued for review (action: {action})",
    )


async def _handle_review_event(payload: WebhookPayload) -> WebhookResponse:
    """Handle pull_request_review events (for learning loop)."""
    # Future: capture human review feedback for few-shot learning
    return WebhookResponse(accepted=True, message="Review event received")


async def _handle_review_comment_event(payload: WebhookPayload) -> WebhookResponse:
    """Handle pull_request_review_comment events."""
    # Future: capture inline comment feedback
    return WebhookResponse(accepted=True, message="Review comment event received")


# Manual trigger endpoint
manual_router = APIRouter(prefix="/api", tags=["manual"])


@manual_router.post("/review", response_model=WebhookResponse)
async def trigger_manual_review(
    pr_url: str,
    provider: Provider = Provider.GITHUB,
    force: bool = False,
) -> WebhookResponse:
    """Manually trigger a review for a PR URL."""
    # Parse PR URL
    # Format: https://github.com/owner/repo/pull/123
    try:
        parts = pr_url.rstrip("/").split("/")
        if provider == Provider.GITHUB:
            owner, repo = parts[-4], parts[-3]
            pr_number = int(parts[-1])
        else:
            raise ValueError("Only GitHub URLs supported currently")
    except (IndexError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid PR URL: {e}")

    # Fetch PR
    try:
        pr = await github_client.get_pull_request(owner, repo, pr_number)
        repository = await github_client.get_repository(owner, repo)
    except GithubException as e:
        raise HTTPException(status_code=404, detail=f"PR not found: {e}")

    pr_id = f"github:{owner}/{repo}#{pr_number}"

    # Check if already reviewed (unless forced)
    if not force and review_queue.is_completed(pr_id):
        return WebhookResponse(
            accepted=False,
            pr_id=pr_id,
            message="Already reviewed. Use force=true to re-review.",
        )

    await review_queue.enqueue(
        pr_id=pr_id,
        provider=provider,
        repository=repository,
        pull_request=pr,
        trigger="manual",
    )

    return WebhookResponse(
        accepted=True,
        pr_id=pr_id,
        message="Manually queued for review",
    )