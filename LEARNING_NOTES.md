# CodeReview Agent — Learning Notes & Interview Prep

> **Read this file from top to bottom before your interview.** Each section builds on the previous one.

---

## 1. Project Overview (30-second pitch)

> "I built a multi-agent code review system that automatically reviews pull requests. It uses 5 specialist agents — Security, Performance, Style, Architecture, Tests — running in parallel, plus an Aggregator that deduplicates and prioritizes findings. It integrates with GitHub via webhooks, posts inline comments and a summary review, and includes a Next.js dashboard for viewing history. The system routes simple PRs to a fast model (Haiku) and complex ones to a powerful model (Sonnet), with full observability via LangSmith and Prometheus."

---

## 2. Architecture Decisions & Trade-offs

### Why Multi-Agent Instead of Single LLM Call?

| Single LLM | Multi-Agent (Chosen) |
|------------|---------------------|
| One giant prompt | Focused, testable prompts per domain |
| Hard to debug which check failed | Clear ownership: Security agent = security findings |
| All-or-nothing failure | Partial results if one agent fails |
| Token waste on irrelevant context | Each agent sees only what it needs |
| Can't route to different models | Simple→Haiku, Complex→Sonku |

**Key insight**: Agents are *specialized prompts with dedicated output schemas*, not autonomous actors. The "agent" pattern here = structured LLM call + parsing + retry logic.

### Why LangGraph for Orchestration?

- **Stateful**: PR context flows through graph nodes
- **Parallel execution**: `asyncio.gather` for specialist agents
- **Retry/fallback**: Built-in `RetryPolicy` per node
- **Observability**: LangSmith traces each node automatically
- **Extensible**: Add new agent = add node + edge, no core changes

### Model Routing Strategy

```python
def _select_model(self, context: PRContext) -> BaseChatModel:
    total_lines = sum(f.additions + f.deletions for f in context.files)
    if total_lines > 500 or len(context.files) > 10:
        return self.model_complex  # Sonnet
    return self.model_simple       # Haiku
```

**Trade-off**: Heuristic-based (lines/files) not perfect, but zero-latency. Alternative: embedding-based complexity classifier (overkill for v1).

### Aggregator Design

The aggregator is itself an LLM call — not deterministic code — because:
- Deduplication requires semantic understanding ("same root cause" ≠ same line)
- Priority adjustment needs context (test file vs core logic)
- Summary generation is naturally generative

**Fallback**: If aggregator fails, simple merge by severity + source agent.

---

## 3. Data Flow Walkthrough

```
1. GitHub webhook → /webhook/github
   ├── Verify HMAC signature
   ├── Parse payload → WebhookPayload
   └── Enqueue ReviewJob (PRContext not built yet)

2. Background worker picks job
   ├── Fetch full PR + file contents (GitHub API)
   ├── Build PRContext (files with diffs, before/after content)
   └── Run specialist agents in parallel

3. Each Specialist Agent:
   ├── Select model (simple/complex)
   ├── Build prompt: system + human(template + context)
   ├── Call LLM with PydanticOutputParser
   ├── Parse JSON → list[Finding]
   └── Return AgentResult(findings, summary, metrics)

4. Aggregator Agent:
   ├── Collect all AgentResults
   ├── Build prompt with all findings as JSON
   ├── Call LLM (always complex model)
   ├── Parse → ReviewResult (deduped findings, summary, stats)
   └── Return

5. Post Results:
   ├── Format findings as GitHub review comments (inline)
   ├── Format summary as review body
   ├── POST to GitHub API
   └── Mark job COMPLETED
```

---

## 4. Key Code Locations (Know These Cold)

| Component | File | What to Explain |
|-----------|------|-----------------|
| **Agent Base Class** | `app/agents/base.py` | `run()`, `_select_model()`, `_parse_findings()`, tracing |
| **Security Agent** | `app/agents/security.py` | System prompt coverage (OWASP Top 10), JSON output format |
| **Aggregator** | `app/agents/aggregator.py` | `aggregate()`, fallback logic, deduplication prompt |
| **Review Queue** | `app/main.py` | `enqueue()`, `_process_job()`, `_build_context()`, `_post_results()` |
| **GitHub Client** | `app/github/client.py` | `get_pull_request()`, `post_review_comment()`, auth modes |
| **Webhook Handler** | `app/github/webhook.py` | Signature verification, action filtering, manual trigger |
| **Schemas** | `app/schemas.py` | Finding, AgentResult, ReviewResult, PRContext |
| **Config** | `app/config.py` | Feature flags, model names, thresholds |

---

## 5. Anticipated Interview Questions & Answers

### Q: "How do you handle false positives from the LLM?"

**A**: Multiple layers:
1. **Prompt engineering**: Explicit "avoid false positives" instructions, few-shot examples in system prompt
2. **Confidence scoring**: Each finding has `confidence: 0.0-1.0`; UI can filter low-confidence
3. **Context-aware severity**: Aggregator reduces severity for test files, config files
4. **Human feedback loop** (planned): `enable_learning_loop` captures accept/reject → few-shot updates
5. **Rule IDs**: Findings reference CWE/OWASP — verifiable, not opaque

### Q: "What if the LLM returns invalid JSON?"

**A**: `PydanticOutputParser` with retry:
```python
# In BaseAgent._parse_findings()
try:
    data = json.loads(extracted_json)
except json.JSONDecodeError:
    # Fallback: wrap raw response as single INFO finding
    return [Finding(..., severity=Severity.INFO, description=response[:500])]
```
Also: `tenacity` retry on LLM call (3 attempts, exponential backoff).

### Q: "How do you prevent prompt injection from malicious PRs?"

**A**:
- PR content goes into *human* message, not system prompt
- System prompt is fixed, no user input
- File content is escaped in template
- Max diff size limit (3000 chars/file, 50k tokens total)
- Future: dedicated prompt injection classifier

### Q: "How does the system scale to 1000 PRs/day?"

**Current**: In-memory queue + single worker (demo scale).
**Production**:
- Replace queue with Redis + Celery or Redis Streams
- Horizontal worker scaling (stateless)
- Rate limiting per repo/installation
- Cache repository conventions, file languages
- Batch GitHub API calls

### Q: "Why not use GitHub Actions for this?"

**A**: GitHub Actions is *infrastructure*, not *intelligence*.
- Actions runs linters/tests (deterministic)
- This runs *semantic analysis* (LLM reasoning)
- Actions can't maintain conversation context across files
- This posts *inline comments with suggestions* — Actions annotations are limited
- This learns from feedback (planned); Actions are static

### Q: "How do you evaluate agent quality?"

**A**: Three-level eval:
1. **Unit**: Golden PR diffs → expected findings (exact match on rule_id + filename)
2. **LLM-as-Judge**: Aggregator output vs human expert ranking (pairwise comparison)
3. **Production**: Track "accepted suggestions" / "dismissed findings" ratio per agent

**Dataset**: 50 real PRs with expert-annotated findings (security, perf, style).

### Q: "What's the cost per PR review?"

**Estimate** (Anthropic, typical 20-file PR):
- 5 specialists × ~2k tokens each = 10k input + 5k output
- Aggregator: 15k input + 2k output
- Total: ~32k tokens ≈ $0.08 (Haiku) / $0.40 (Sonnet)
- 90% route to Haiku → **~$0.10/PR average**

### Q: "How do you handle large files / monorepos?"

**A**:
- Per-file diff truncation (3000 chars)
- Max 50 files/PR, 50k total diff tokens
- Skip files > 100KB (configurable)
- Language detection → skip non-code (images, lockfiles)
- Future: AST-based chunking for huge files

### Q: "What's the hardest technical challenge you solved?"

**A**: **Aggregator deduplication**.
- Problem: Security agent finds "hardcoded secret line 45", Style agent finds "magic string line 45" — same issue, different categories
- Solution: LLM-based semantic merge with `source_agents` tracking
- Key prompt: "Same root cause = same file, overlapping lines, related CWE"
- Fallback: deterministic merge by (filename, line_range) if LLM fails

---

## 6. "Why This Project?" — Narrative

> "I wanted to build something that solves a real engineering pain point — code review is slow, inconsistent, and seniors are bottlenecks. I chose this because:
> 1. **Technical depth**: Agents, orchestration, structured output, model routing, observability
> 2. **Product thinking**: Webhook → queue → async worker → GitHub API → dashboard
> 3. **Domain relevance**: Every software company needs this; Axis Bank's Enterprise AI Group builds exactly this kind of platform
> 4. **Extensibility**: Plugin architecture for new agents, new git providers, new LLM providers
> 5. **Dogfoodable**: I run it on my own repos — it catches real issues"

---

## 7. Future Improvements (Shows Vision)

| Feature | Effort | Value |
|---------|--------|-------|
| **Learning Loop** | Medium | Few-shot from human feedback → continuously improving |
| **Custom Rules DSL** | Medium | Teams define org-specific patterns (regex + LLM) |
| **PR Description Generator** | Low | Auto-write PR description from commits |
| **Cross-Repo Consistency** | High | Org-wide convention learning |
| **IDE Integration** | Medium | VS Code extension for pre-commit review |
| **Multi-Language AST Parsing** | High | Precise line mapping, symbol resolution |

---

## 8. Quick Reference: File → Class → Method

```
app/agents/base.py
  BaseAgent.run() → _select_model() → _build_context() → _parse_findings()
  AgentRegistry.register() → get_enabled()

app/agents/security.py
  SecurityAgent.system_prompt (OWASP Top 10 coverage)

app/agents/aggregator.py
  AggregatorAgent.aggregate() → _parse_aggregated() → _fallback_aggregate()

app/main.py
  ReviewQueue.enqueue() → _worker() → _process_job() → _build_context()
  → _run_specialist_agents() → _post_results() → _format_comments()

app/github/client.py
  GitHubClient.get_pull_request() → post_review_comment() → create_review_summary()

app/github/webhook.py
  github_webhook() → _handle_pull_request_event() → trigger_manual_review()

app/schemas.py
  Finding, AgentResult, ReviewResult, PRContext, WebhookPayload
```

---

## 9. Run Commands Cheat Sheet

```bash
# Backend
poetry install
poetry run python -m app          # Dev server
poetry run pytest -v              # Tests
poetry run ruff check .           # Lint
poetry run mypy app/              # Type check

# Frontend
cd frontend
npm install
npm run dev                       # http://localhost:3000

# Docker
docker-compose up --build         # All services
docker build -t codereview-agent .
docker run -p 8000:8000 --env-file .env codereview-agent

# Webhook testing (ngrok)
ngrok http 8000
# Set GitHub webhook to https://xxx.ngrok.io/webhook/github
```

---

## 10. One-Liners for Rapid Fire

- **Agent pattern**: "Specialized prompt + structured output + retry + tracing = agent"
- **Orchestration**: "LangGraph for state, asyncio for parallelism, fallback for resilience"
- **Model routing**: "Heuristic by diff size; 90% Haiku, 10% Sonnet; 10x cost savings"
- **Deduplication**: "LLM-based semantic merge with source tracking; deterministic fallback"
- **GitHub integration": "Webhook → queue → async worker → review comments + summary review"
- **Observability**: "LangSmith traces, Prometheus metrics, structured JSON logs"
- **Security": "HMAC verification, PAT/App auth, no secrets in logs, input size limits"
- **Extensibility": "AgentRegistry + feature flags + plugin interface for new checkers"

---

## 11. If Asked to Whiteboard

**Draw**:
1. Webhook → Queue → Worker (boxes)
2. Worker → 5 parallel agents → Aggregator (fan-out/fan-in)
3. Aggregator → GitHub API (comments + review)
4. Dashboard ← API ← Queue (read path)

**Label**: Async boundaries, retry points, where metrics emitted, where traces start/end.

---

## 12. Final Confidence Check

Can you explain, *without looking at code*:
- [ ] How a PR gets from webhook to posted comment
- [ ] Why 5 specialist agents + 1 aggregator
- [ ] How model routing works and why
- [ ] How findings are deduplicated
- [ ] How the system handles LLM failures
- [ ] How you'd scale from 10 to 10,000 PRs/day
- [ ] What the dashboard shows and how it fetches data
- [ ] One thing you'd improve with 2 more weeks

**If yes to all → you're ready.**

---

*Generated as part of CodeReview Agent project. Update as you learn.*