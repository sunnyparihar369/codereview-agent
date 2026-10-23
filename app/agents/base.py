"""Base agent class with common functionality."""

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langsmith import traceable
from pydantic import BaseModel

from app.config import get_settings
from app.schemas import AgentName, AgentResult, Finding, FindingCategory, PRContext, Severity

settings = get_settings()


class BaseAgent(ABC):
    """Base class for all specialist review agents."""

    def __init__(
        self,
        name: AgentName,
        model_simple: BaseChatModel,
        model_complex: BaseChatModel,
        category: FindingCategory,
    ) -> None:
        self.name = name
        self.model_simple = model_simple
        self.model_complex = model_complex
        self.category = category
        self.parser = PydanticOutputParser(pydantic_object=Finding)

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt for this agent."""
        pass

    @property
    @abstractmethod
    def human_prompt_template(self) -> str:
        """Human prompt template with {context} placeholder."""
        pass

    def _select_model(self, context: PRContext) -> BaseChatModel:
        """Select model based on PR complexity."""
        total_lines = sum(f.additions + f.deletions for f in context.files)
        if total_lines > 500 or len(context.files) > 10:
            return self.model_complex
        return self.model_simple

    def _build_context(self, context: PRContext) -> str:
        """Build context string for the prompt."""
        parts = [
            f"Repository: {context.repository.full_name}",
            f"PR #{context.pull_request.number}: {context.pull_request.title}",
            f"Description: {context.pull_request.body or 'No description'}",
            f"Files changed: {len(context.files)}",
            "",
        ]

        for f in context.files:
            parts.append(f"=== {f.filename} (+{f.additions}/-{f.deletions}) ===")
            parts.append(f"Language: {f.language or 'unknown'}")
            if f.diff:
                # Truncate large diffs
                diff = f.diff
                if len(diff) > 3000:
                    diff = diff[:3000] + "\n... (truncated)"
                parts.append(f"Diff:\n{diff}")
            parts.append("")

        return "\n".join(parts)

    @traceable(name="agent_run", run_type="chain")
    async def run(self, context: PRContext) -> AgentResult:
        """Run the agent on the PR context."""
        start_time = time.time()
        model = self._select_model(context)
        context_str = self._build_context(context)

        try:
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=self.human_prompt_template.format(context=context_str)),
            ]

            response = await model.ainvoke(messages)

            # Parse findings from response
            findings = self._parse_findings(response.content, context)

            return AgentResult(
                agent=self.name,
                findings=findings,
                summary=self._generate_summary(findings),
                processing_time_ms=int((time.time() - start_time) * 1000),
                tokens_used=self._estimate_tokens(messages, response.content),
                model_used=model.model_name if hasattr(model, "model_name") else "unknown",
            )
        except Exception as e:
            return AgentResult(
                agent=self.name,
                findings=[],
                summary=f"Agent error: {str(e)}",
                processing_time_ms=int((time.time() - start_time) * 1000),
                tokens_used=0,
                model_used="error",
                errors=[str(e)],
            )

    def _parse_findings(self, response: str, context: PRContext) -> list[Finding]:
        """Parse findings from LLM response."""
        findings = []

        # Try to parse as JSON array of findings
        import json

        try:
            # Extract JSON from response
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                for item in data:
                    if isinstance(item, dict):
                        finding = Finding(
                            id=str(uuid.uuid4())[:8],
                            agent=self.name,
                            category=self.category,
                            **item,
                        )
                        findings.append(finding)
        except (json.JSONDecodeError, ValueError):
            # Fallback: create a single finding from the response
            if response.strip():
                findings.append(
                    Finding(
                        id=str(uuid.uuid4())[:8],
                        agent=self.name,
                        category=self.category,
                        severity=Severity.INFO,
                        title="Agent Analysis",
                        description=response[:500],
                        filename=context.files[0].filename if context.files else "unknown",
                    )
                )

        return findings

    def _generate_summary(self, findings: list[Finding]) -> str:
        """Generate a summary of findings."""
        if not findings:
            return f"No {self.category.value} issues found."

        by_severity: dict[Severity, int] = {}
        for f in findings:
            by_severity[f.severity] = by_severity.get(f.severity, 0) + 1

        parts = [f"Found {len(findings)} {self.category.value} issue(s):"]
        for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
            if sev in by_severity:
                parts.append(f"  {sev.value}: {by_severity[sev]}")
        return "\n".join(parts)

    def _estimate_tokens(self, messages: list, response: str) -> int:
        """Rough token estimation."""
        import tiktoken

        try:
            enc = tiktoken.get_encoding("cl100k_base")
            total = sum(len(enc.encode(m.content)) for m in messages)
            total += len(enc.encode(response))
            return total
        except Exception:
            return 0


class AgentRegistry:
    """Registry for all available agents."""

    def __init__(self) -> None:
        self._agents: dict[AgentName, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: AgentName) -> BaseAgent | None:
        return self._agents.get(name)

    def get_enabled(self, settings) -> list[BaseAgent]:
        """Get all enabled agents based on settings."""
        enabled = []
        flag_map = {
            AgentName.SECURITY: settings.enable_security_agent,
            AgentName.PERFORMANCE: settings.enable_performance_agent,
            AgentName.STYLE: settings.enable_style_agent,
            AgentName.ARCHITECTURE: settings.enable_architecture_agent,
            AgentName.TESTS: settings.enable_tests_agent,
        }
        for name, enabled_flag in flag_map.items():
            if enabled_flag and name in self._agents:
                enabled.append(self._agents[name])
        return enabled

    def all_names(self) -> list[AgentName]:
        return list(self._agents.keys())