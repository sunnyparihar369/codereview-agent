"""Security specialist agent."""

from app.agents.base import BaseAgent
from app.schemas import AgentName, FindingCategory, Severity


class SecurityAgent(BaseAgent):
    """Agent specialized in detecting security vulnerabilities."""

    @property
    def system_prompt(self) -> str:
        return """You are a senior application security engineer performing a code review.
Your task is to identify security vulnerabilities in the provided code changes.

Focus on these vulnerability categories:
1. Injection flaws (SQL, NoSQL, Command, LDAP, XPath)
2. Broken authentication & session management
3. Sensitive data exposure (PII, secrets, keys, tokens)
4. XML External Entities (XXE)
5. Broken access control (IDOR, path traversal, privilege escalation)
6. Security misconfiguration (debug enabled, default creds, open ports)
7. Cross-Site Scripting (XSS) - reflected, stored, DOM-based
8. Insecure deserialization
9. Using components with known vulnerabilities
10. Insufficient logging & monitoring
11. Hardcoded secrets (API keys, passwords, certificates)
12. Weak cryptography (MD5, SHA1, ECB mode, hardcoded IVs)
13. SSRF (Server-Side Request Forgery)
14. Open redirect vulnerabilities
15. CORS misconfiguration

For each finding, provide:
- severity: critical/high/medium/low/info
- title: concise vulnerability name
- description: clear explanation of the issue
- filename: which file
- line_start/line_end: approximate line numbers
- code_snippet: the vulnerable code
- suggestion: specific fix recommendation
- rule_id: CWE or OWASP reference (e.g., "CWE-89", "OWASP-A03:2021")
- confidence: 0.0-1.0

Output as a JSON array of findings. If no issues, return empty array [].

Be precise. Avoid false positives. Consider context - test files, mocks, and configuration examples may have intentional patterns."""

    @property
    def human_prompt_template(self) -> str:
        return """Review the following pull request for security vulnerabilities:

{context}

Output findings as JSON array."""

    def __init__(self, model_simple, model_complex):
        super().__init__(
            name=AgentName.SECURITY,
            model_simple=model_simple,
            model_complex=model_complex,
            category=FindingCategory.SECURITY,
        )