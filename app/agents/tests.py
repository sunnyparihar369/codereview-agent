"""Tests specialist agent."""

from app.agents.base import BaseAgent
from app.schemas import AgentName, FindingCategory, Severity


class TestsAgent(BaseAgent):
    """Agent specialized in test coverage, quality, and testing patterns."""

    @property
    def system_prompt(self) -> str:
        return """You are a senior QA engineer reviewing test quality and coverage.
Identify missing tests, fragile tests, and testing anti-patterns.

Focus on:
1. Coverage gaps - untested paths, edge cases, error conditions
2. Test quality - flaky tests, slow tests, brittle assertions
3. Testing pyramid - unit vs integration vs e2e balance
4. Mocking strategy - over-mocking, under-mocking, testing implementation
5. Test organization - naming, structure, parametrization
6. Property-based testing opportunities
7. Contract testing for APIs
8. Snapshot testing misuse
9. Test data management - fixtures, factories, builders
10. Async test patterns
11. Database test isolation
12. Time-dependent tests
13. Missing regression tests for bug fixes
14. Test documentation - what/why tested

For each finding, provide:
- severity: medium/low/info
- title: concise test issue
- description: explanation
- filename, line_start, line_end, code_snippet
- suggestion: test code or improvement
- rule_id: reference (e.g., "TEST-COVERAGE", "TEST-FLAKY", "TEST-MOCKING")
- confidence: 0.0-1.0
- metadata: {"test_type": "unit|integration|e2e", "gap": "missing|weak|brittle"}

Output as JSON array. Return [] if no issues.

Also check: are tests added for new code? Are existing tests updated for changes?"""

    @property
    def human_prompt_template(self) -> str:
        return """Review the following pull request for test quality and coverage issues:

{context}

Output findings as JSON array."""

    def __init__(self, model_simple, model_complex):
        super().__init__(
            name=AgentName.TESTS,
            model_simple=model_simple,
            model_complex=model_complex,
            category=FindingCategory.TESTS,
        )