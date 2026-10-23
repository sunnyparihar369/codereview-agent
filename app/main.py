"""Review queue for managing PR review jobs."""

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.config import get_settings
from app.github.client import GitHubClient
from app.schemas import AgentName, AgentResult, PRContext, Provider, PullRequest, ReviewResult, ReviewStatus
from app.agents import (
    AgentRegistry,
    AggregatorAgent,
    ArchitectureAgent,
    PerformanceAgent,
    SecurityAgent,
    StyleAgent,
    TestsAgent,
)

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ReviewJob:
    """A queued review job."""

    pr_id: str
    provider: Provider
    repository: Any  # GitRepository
    pull_request: PullRequest
    installation_id: int | None = None
    trigger: str = "webhook"
    status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: ReviewResult | None = None
    error: str | None = None
    retry_count: int = 0


class ReviewQueue:
    """In-memory review queue with background worker."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[ReviewJob] = asyncio.Queue()
        self._jobs: dict[str, ReviewJob] = {}
        self._worker_task: asyncio.Task | None = None
        self._running = False
        self._github_client = GitHubClient()
        self._agent_registry = self._build_agent_registry()
        self._aggregator: AggregatorAgent | None = None
        self._llm_models: dict[str, Any] = {}

    def _build_agent_registry(self) -> AgentRegistry:
        """Build and populate agent registry."""
        registry = AgentRegistry()
        # Agents will be initialized with models in initialize()
        return registry

    async def initialize(self, models: dict[str, Any]) -> None:
        """Initialize agents with LLM models."""
        self._llm_models = models
        model_simple = models["simple"]
        model_complex = models["complex"]

        # Register specialist agents
        self._agent_registry.register(SecurityAgent(model_simple, model_complex))
        self._agent_registry.register(PerformanceAgent(model_simple, model_complex))
        self._agent_registry.register(StyleAgent(model_simple, model_complex))
        self._agent_registry.register(ArchitectureAgent(model_simple, model_complex))
        self._agent_registry.register(TestsAgent(model_simple, model_complex))

        # Initialize aggregator
        self._aggregator = AggregatorAgent(model_simple, model_complex)

    async def start(self) -> None:
        """Start the background worker."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Review queue worker started")

    async def stop(self) -> None:
        """Stop the background worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Review queue worker stopped")

    async def enqueue(
        self,
        pr_id: str,
        provider: Provider,
        repository: Any,
        pull_request: PullRequest,
        installation_id: int | None = None,
        trigger: str = "webhook",
    ) -> str:
        """Add a review job to the queue."""
        # Check if already queued or in progress
        if pr_id in self._jobs:
            existing = self._jobs[pr_id]
            if existing.status in (ReviewStatus.PENDING, ReviewStatus.IN_PROGRESS):
                logger.info("PR %s already queued/in progress, skipping", pr_id)
                return pr_id

        job = ReviewJob(
            pr_id=pr_id,
            provider=provider,
            repository=repository,
            pull_request=pull_request,
            installation_id=installation_id,
            trigger=trigger,
        )
        self._jobs[pr_id] = job
        await self._queue.put(job)
        logger.info("Enqueued review for %s (trigger: %s)", pr_id, trigger)
        return pr_id

    def is_completed(self, pr_id: str) -> bool:
        """Check if a PR has been reviewed."""
        job = self._jobs.get(pr_id)
        return job is not None and job.status == ReviewStatus.COMPLETED

    def get_job(self, pr_id: str) -> ReviewJob | None:
        """Get job by ID."""
        return self._jobs.get(pr_id)

    def get_all_jobs(self, limit: int = 50) -> list[ReviewJob]:
        """Get recent jobs."""
        jobs = list(self._jobs.values())
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    async def _worker(self) -> None:
        """Background worker processing review jobs."""
        while self._running:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._process_job(job)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error("Worker error: %s", e)
                await asyncio.sleep(1)

    async def _process_job(self, job: ReviewJob) -> None:
        """Process a single review job."""
        job.status = ReviewStatus.IN_PROGRESS
        job.started_at = datetime.utcnow()
        logger.info("Starting review for %s", job.pr_id)

        try:
            # Build PR context
            context = await self._build_context(job)

            # Run specialist agents
            agent_results = await self._run_specialist_agents(context)

            # Aggregate results
            if self._aggregator:
                review_result = await self._aggregator.aggregate(context, agent_results)
            else:
                review_result = self._fallback_aggregate(agent_results)

            review_result.pr_id = job.pr_id
            review_result.completed_at = datetime.utcnow()
            if job.started_at:
                review_result.total_time_ms = int(
                    (review_result.completed_at - job.started_at).total_seconds() * 1000
                )

            # Post results to GitHub
            await self._post_results(job, review_result)

            job.result = review_result
            job.status = ReviewStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            logger.info("Completed review for %s: %d findings", job.pr_id, len(review_result.all_findings))

        except Exception as e:
            job.status = ReviewStatus.FAILED
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            logger.error("Review failed for %s: %s", job.pr_id, e)

            # Post error comment
            await self._post_error(job, str(e))

    async def _build_context(self, job: ReviewJob) -> PRContext:
        """Build PR context from job data."""
        pr = job.pull_request
        files = []

        for f in pr.files:
            # Determine language from extension
            language = self._detect_language(f.filename)

            # Fetch file content before/after if needed
            content_before = None
            content_after = None
            if job.provider == Provider.GITHUB and job.installation_id:
                content_before = await self._github_client.get_file_content(
                    job.repository.owner.login,
                    job.repository.name,
                    f.filename,
                    pr.base.sha,
                    job.installation_id,
                )
                content_after = await self._github_client.get_file_content(
                    job.repository.owner.login,
                    job.repository.name,
                    f.filename,
                    pr.head.sha,
                    job.installation_id,
                )

            files.append(
                PRContext.model_fields["files"].annotation.__args__[0](  # type: ignore
                    filename=f.filename,
                    language=language,
                    content_before=content_before,
                    content_after=content_after,
                    diff=f.patch or "",
                    additions=f.additions,
                    deletions=f.deletions,
                    line_count=f.additions + f.deletions,
                )
            )

        return PRContext(
            pr_id=job.pr_id,
            provider=job.provider,
            repository=job.repository,
            pull_request=pr,
            files=files,
        )

    def _detect_language(self, filename: str) -> str | None:
        """Detect programming language from filename."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".c": "c",
            ".h": "c",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".sql": "sql",
            ".sh": "bash",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".md": "markdown",
            ".dockerfile": "dockerfile",
            ".tf": "terraform",
        }
        for ext, lang in ext_map.items():
            if filename.endswith(ext):
                return lang
        return None

    async def _run_specialist_agents(self, context: PRContext) -> dict[AgentName, AgentResult]:
        """Run all enabled specialist agents in parallel."""
        agents = self._agent_registry.get_enabled(settings)
        results = {}

        # Run agents concurrently
        tasks = {agent.name: agent.run(context) for agent in agents}
        for name, task in tasks.items():
            results[name] = await task

        return results

    def _fallback_aggregate(self, agent_results: dict[AgentName, AgentResult]) -> ReviewResult:
        """Fallback aggregation if aggregator fails."""
        all_findings = []
        stats = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "by_category": {}, "by_file": {}}

        for agent_name, result in agent_results.items():
            for finding in result.findings:
                finding.metadata["source_agent"] = agent_name.value
                all_findings.append(finding)
                stats[finding.severity.value] += 1
                stats["by_category"][finding.category.value] = stats["by_category"].get(finding.category.value, 0) + 1
                stats["by_file"][finding.filename] = stats["by_file"].get(finding.filename, 0) + 1

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        all_findings.sort(key=lambda f: severity_order.get(f.severity.value, 5))

        return ReviewResult(
            pr_id="",
            status=ReviewStatus.COMPLETED,
            agent_results=agent_results,
            all_findings=all_findings,
            summary=f"Aggregated {len(all_findings)} findings from {len(agent_results)} agents (fallback mode).",
            stats=stats,
        )

    async def _post_results(self, job: ReviewJob, result: ReviewResult) -> None:
        """Post review results to GitHub."""
        if job.provider != Provider.GITHUB:
            return

        try:
            # Prepare comments
            comments = self._format_comments(result)
            if comments:
                await self._github_client.post_review_comment(
                    job.repository.owner.login,
                    job.repository.name,
                    job.pull_request.number,
                    comments,
                    job.installation_id,
                )

            # Post summary review
            summary_body = self._format_summary(result)
            await self._github_client.create_review_summary(
                job.repository.owner.login,
                job.repository.name,
                job.pull_request.number,
                summary_body,
                event="COMMENT",
                installation_id=job.installation_id,
            )

        except Exception as e:
            logger.error("Failed to post results for %s: %s", job.pr_id, e)

    def _format_comments(self, result: ReviewResult) -> list[dict]:
        """Format findings as GitHub review comments."""
        comments = []
        for finding in result.all_findings:
            if finding.line_start and finding.filename:
                body = f"**[{finding.severity.value.upper()}] {finding.title}**\n\n"
                body += f"{finding.description}\n\n"
                if finding.suggestion:
                    body += f"**Suggestion:**\n```suggestion\n{finding.suggestion}\n```\n\n"
                if finding.rule_id:
                    body += f"*Rule: {finding.rule_id}*"
                if finding.metadata.get("source_agent"):
                    body += f"  \n*Detected by: {finding.metadata['source_agent']} agent*"

                comments.append(
                    {
                        "path": finding.filename,
                        "line": finding.line_start,
                        "side": "RIGHT",
                        "body": body,
                    }
                )
        return comments

    def _format_summary(self, result: ReviewResult) -> str:
        """Format summary as GitHub review body."""
        stats = result.stats
        lines = [
            f"## 🤖 CodeReview Agent Summary",
            f"",
            f"**Total Findings:** {len(result.all_findings)}",
            f"",
            f"### By Severity",
            f"- 🔴 Critical: {stats.get('critical', 0)}",
            f"- 🟠 High: {stats.get('high', 0)}",
            f"- 🟡 Medium: {stats.get('medium', 0)}",
            f"- 🟢 Low: {stats.get('low', 0)}",
            f"- ℹ️ Info: {stats.get('info', 0)}",
            f"",
        ]

        if stats.get("by_category"):
            lines.append("### By Category")
            for cat, count in stats["by_category"].items():
                lines.append(f"- {cat}: {count}")
            lines.append("")

        if stats.get("by_file"):
            lines.append("### By File")
            for file, count in sorted(stats["by_file"].items(), key=lambda x: -x[1])[:10]:
                lines.append(f"- `{file}`: {count}")
            lines.append("")

        lines.append("---")
        lines.append(result.summary)
        lines.append("")
        lines.append(f"*Review completed in {result.total_time_ms}ms • {result.total_tokens} tokens*")

        return "\n".join(lines)

    async def _post_error(self, job: ReviewJob, error: str) -> None:
        """Post error comment to PR."""
        if job.provider != Provider.GITHUB:
            return

        try:
            body = f"## ❌ CodeReview Agent Error\n\nFailed to complete review: `{error}`\n\nPlease check the agent logs."
            await self._github_client.create_review_summary(
                job.repository.owner.login,
                job.repository.name,
                job.pull_request.number,
                body,
                event="COMMENT",
                installation_id=job.installation_id,
            )
        except Exception as e:
            logger.error("Failed to post error for %s: %s", job.pr_id, e)


# Global queue instance
review_queue = ReviewQueue()