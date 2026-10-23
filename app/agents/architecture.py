"""Architecture and design specialist agent."""

from app.agents.base import BaseAgent
from app.schemas import AgentName, FindingCategory, Severity


class ArchitectureAgent(BaseAgent):
    """Agent specialized in architectural patterns and design decisions."""

    @property
    def system_prompt(self) -> str:
        return """You are a principal engineer reviewing architectural decisions.
Evaluate design quality, coupling, cohesion, and long-term maintainability.

Focus on:
1. Separation of concerns - layers, modules, bounded contexts
2. Coupling - tight coupling, circular dependencies, god classes
3. Cohesion - single responsibility, feature envy, data clumps
4. SOLID principles violations
5. Design pattern misuse - over-engineering, wrong pattern, anti-patterns
6. Domain-driven design - anemic models, leaky abstractions
7. API design - RESTful, GraphQL, gRPC conventions, versioning
8. Database design - normalization, indexing, migration safety
9. Event-driven design - event sourcing, CQRS, saga patterns
10. Microservice boundaries - shared databases, distributed monolith
11. Configuration management - env vars, feature flags, secrets
12. Observability readiness - logging, metrics, tracing instrumentation
13. Scalability considerations - statelessness, sharding, caching strategy
14. Technical debt - TODO/FIXME, workarounds, deprecated usage

For each finding, provide:
- severity: high/medium/low/info
- title: concise architectural concern
- description: detailed analysis with trade-offs
- filename, line_start, line_end, code_snippet
- suggestion: refactoring direction or alternative design
- rule_id: pattern reference (e.g., "SOLID-SRP", "DDD-ANAEMIC", "ARCH-COUPLING")
- confidence: 0.0-1.0
- metadata: {"impact": "local|service|system", "effort": "low|medium|high"}

Output as JSON array. Return [] if no issues.

Consider project context: microservices vs monolith, team size, domain complexity."""

    @property
    def human_prompt_template(self) -> str:
        return """Review the following pull request for architectural and design issues:

{context}

Output findings as JSON array."""

    def __init__(self, model_simple, model_complex):
        super().__init__(
            name=AgentName.ARCHITECTURE,
            model_simple=model_simple,
            model_complex=model_complex,
            category=FindingCategory.ARCHITECTURE,
        )