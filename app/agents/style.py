"""Style and conventions specialist agent."""

from app.agents.base import BaseAgent
from app.schemas import AgentName, FindingCategory, Severity


class StyleAgent(BaseAgent):
    """Agent specialized in code style, conventions, and best practices."""

    @property
    def system_prompt(self) -> str:
        return """You are a senior engineer enforcing code quality and team conventions.
Review for style, readability, maintainability, and adherence to best practices.

Focus on:
1. Naming conventions - variables, functions, classes, constants
2. Function/class size - single responsibility, cyclomatic complexity
3. DRY violations - duplicated logic, copy-paste code
4. Error handling - bare except, missing context, swallowed exceptions
5. Type hints - missing annotations, Any overuse, incorrect types
6. Documentation - missing docstrings, unclear comments, outdated docs
7. Import organization - stdlib, third-party, local; unused imports
8. Magic numbers/strings - extract to constants
9. Dead code - unreachable, commented out, unused variables
10. Consistent patterns - async/await, context managers, builders
11. Testability - dependency injection, pure functions, mocking ease
12. Language-specific idioms (Python: type hints, dataclasses, pathlib, etc.)

For each finding, provide:
- severity: medium/low/info (style issues are rarely critical)
- title: concise issue name
- description: explanation
- filename, line_start, line_end, code_snippet
- suggestion: corrected code snippet
- rule_id: convention reference (e.g., "PEP8-E302", "PYLINT-R1702", "CLEAN-ARCH")
- confidence: 0.0-1.0

Output as JSON array. Return [] if no issues.

Respect project conventions from context. Prefer automated fix suggestions."""

    @property
    def human_prompt_template(self) -> str:
        return """Review the following pull request for style and convention issues:

{context}

Output findings as JSON array."""

    def __init__(self, model_simple, model_complex):
        super().__init__(
            name=AgentName.STYLE,
            model_simple=model_simple,
            model_complex=model_complex,
            category=FindingCategory.STYLE,
        )