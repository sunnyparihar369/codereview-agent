"""Aggregator agent - combines and prioritizes findings from all specialists."""

import json
from typing import Any

from app.agents.base import BaseAgent
from app.schemas import AgentName, AgentResult, Finding, FindingCategory, PRContext, ReviewResult, Severity


class AggregatorAgent(BaseAgent):
    """Aggregates, deduplicates, and prioritizes findings from all specialist agents."""

    @property
    def system_prompt(self) -> str:
        return """You are the lead reviewer aggregating findings from specialist agents.
Your job: deduplicate, prioritize, and create a coherent review summary.

Rules:
1. DEDUPLICATE: Merge findings that point to the same issue (same file, similar lines, same root cause)
   - Keep the highest severity
   - Merge descriptions
   - Combine suggestions
   - Track which agents caught it

2. PRIORITIZE: Order by severity (critical > high > medium > low > info), then by impact

3. CONTEXTUALIZE: Adjust severity based on context:
   - Test files: reduce severity by 1 level (except security)
   - Config/generated files: reduce severity
   - Core business logic: increase severity for critical/high

4. CREATE SUMMARY: Write a concise executive summary for the PR author

5. ACTIONABLE OUTPUT: Group findings by file for easy navigation

Output as JSON with this structure:
{
  "findings": [...],  // deduplicated, prioritized findings with added "source_agents" field
  "summary": "Executive summary string",
  "stats": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "by_category": {...}, "by_file": {...}}
}"""

    @property
    def human_prompt_template(self) -> str:
        return """Aggregate the following specialist agent results for this PR:

{context}

SPECIALIST FINDINGS:
{specialist_findings}

Output aggregated results as JSON."""

    def __init__(self, model_simple, model_complex):
        super().__init__(
            name=AgentName.AGGREGATOR,
            model_simple=model_simple,
            model_complex=model_complex,
            category=FindingCategory.MAINTAINABILITY,  # Not used for aggregator
        )

    async def aggregate(self, pr_context: PRContext, agent_results: dict[AgentName, AgentResult]) -> ReviewResult:
        """Aggregate all agent results into a final review."""
        # Prepare specialist findings for the prompt
        specialist_data = {}
        for name, result in agent_results.items():
            if result.findings:
                specialist_data[name.value] = [
                    {
                        "severity": f.severity.value,
                        "title": f.title,
                        "description": f.description,
                        "filename": f.filename,
                        "line_start": f.line_start,
                        "line_end": f.line_end,
                        "code_snippet": f.code_snippet,
                        "suggestion": f.suggestion,
                        "rule_id": f.rule_id,
                        "confidence": f.confidence,
                        "category": f.category.value,
                    }
                    for f in result.findings
                ]

        # Build context
        context_str = self._build_context(pr_context)
        specialist_str = json.dumps(specialist_data, indent=2)

        model = self.model_complex  # Always use complex for aggregation
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.human_prompt_template.format(context=context_str, specialist_findings=specialist_str)},
        ]

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            response = await model.ainvoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=self.human_prompt_template.format(context=context_str, specialist_findings=specialist_str)),
            ])

            # Parse aggregated result
            return self._parse_aggregated(response.content, agent_results)
        except Exception as e:
            # Fallback: simple merge
            return self._fallback_aggregate(agent_results, str(e))

    def _parse_aggregated(self, response: str, agent_results: dict[AgentName, AgentResult]) -> ReviewResult:
        """Parse aggregated response."""
        import json
        import uuid

        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])

                findings = []
                for item in data.get("findings", []):
                    source_agents = item.pop("source_agents", [])
                    finding = Finding(
                        id=str(uuid.uuid4())[:8],
                        agent=AgentName.AGGREGATOR,
                        source_agents=source_agents,  # type: ignore
                        **item,
                    )
                    findings.append(finding)

                return ReviewResult(
                    pr_id="",  # Will be set by caller
                    status="completed",
                    agent_results=agent_results,
                    all_findings=findings,
                    summary=data.get("summary", "Review completed."),
                    stats=data.get("stats", {}),
                )
        except Exception:
            pass

        return self._fallback_aggregate(agent_results, "Parse failed")

    def _fallback_aggregate(
        self, agent_results: dict[AgentName, AgentResult], error: str
    ) -> ReviewResult:
        """Simple fallback aggregation."""
        all_findings = []
        stats = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "by_category": {}, "by_file": {}}

        for agent_name, result in agent_results.items():
            for finding in result.findings:
                # Add source agent info
                finding.metadata["source_agent"] = agent_name.value
                all_findings.append(finding)

                # Update stats
                stats[finding.severity.value] += 1
                stats["by_category"][finding.category.value] = stats["by_category"].get(finding.category.value, 0) + 1
                stats["by_file"][finding.filename] = stats["by_file"].get(finding.filename, 0) + 1

        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        all_findings.sort(key=lambda f: severity_order.get(f.severity.value, 5))

        return ReviewResult(
            pr_id="",
            status="completed",
            agent_results=agent_results,
            all_findings=all_findings,
            summary=f"Aggregated {len(all_findings)} findings from {len(agent_results)} agents. Note: {error}",
            stats=stats,
        )