# CodeReview Agent

Multi-agent automated code review system for enterprise repositories. Built with FastAPI, LangGraph, and Next.js.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      CodeReview Agent                            │
├─────────────────────────────────────────────────────────────────┤
│  Webhook (GitHub/GitLab) → Queue → PR Context Builder           │
└─────────────────────┬───────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Specialist Agents (Parallel)                  │
│  ┌──────────┐ ┌────────────┐ ┌───────┐ ┌────────────┐ ┌──────┐  │
│  │ Security │ │ Performance│ │ Style │ │Architecture│ │Tests │  │
│  └──────────┘ └────────────┘ └───────┘ └────────────┘ └──────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Aggregator Agent                            │
│  Deduplicate → Prioritize → Contextualize → Summary             │
└─────────────────────┬───────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  Post Results → GitHub Review Comments + Summary Review         │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **5 Specialist Agents**: Security, Performance, Style, Architecture, Tests
- **Smart Aggregation**: Deduplicates findings, prioritizes by severity, adjusts for context
- **GitHub Integration**: Webhook-triggered reviews, inline comments, summary reviews
- **Multi-Model Routing**: Simple changes → fast model; complex PRs → powerful model
- **Observability**: LangSmith tracing, Prometheus metrics, structured logging
- **Dashboard**: Next.js 14 frontend for viewing review history and findings
- **Production Ready**: Docker, CI/CD, health checks, graceful shutdown

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Poetry (Python dependency management)
- GitHub App or Personal Access Token
- LLM API key (Anthropic, OpenAI, or Gemini)

### Backend Setup

```bash
# Clone and enter
git clone <your-repo>
cd codereview-agent

# Copy env template
cp .env.example .env
# Edit .env with your credentials

# Install dependencies
poetry install

# Run locally
poetry run python -m app
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Docker

```bash
# Development
docker-compose up --build

# Production
docker build -t codereview-agent .
docker run -p 8000:8000 --env-file .env codereview-agent
```

## Configuration

Key environment variables (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `GITHUB_APP_ID` / `GITHUB_APP_PRIVATE_KEY` | GitHub App authentication (recommended) |
| `GITHUB_TOKEN` | Personal access token (alternative) |
| `GITHUB_WEBHOOK_SECRET` | Webhook signature verification |
| `DEFAULT_LLM_PROVIDER` | `anthropic`, `openai`, or `gemini` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` | LLM provider keys |
| `LANGSMITH_API_KEY` | Enable LangSmith tracing |
| `MODEL_SIMPLE` / `MODEL_COMPLEX` | Model names for routing |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhook/github` | GitHub webhook receiver |
| `POST` | `/api/review` | Manually trigger review |
| `GET` | `/api/jobs` | List recent review jobs |
| `GET` | `/api/jobs/{pr_id}` | Get job details |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |

## Agent Details

### Security Agent
Detects: SQL injection, XSS, hardcoded secrets, weak crypto, path traversal, SSRF, insecure deserialization, auth bypasses.

### Performance Agent
Detects: N+1 queries, O(n²) loops, memory leaks, blocking async code, missing indexes, unbounded caches, ReDoS.

### Style Agent
Enforces: Naming conventions, function size, DRY, error handling, type hints, imports, dead code, language idioms.

### Architecture Agent
Evaluates: Coupling/cohesion, SOLID, DDD, API design, database design, microservice boundaries, observability.

### Tests Agent
Checks: Coverage gaps, flaky tests, mocking strategy, test pyramid, async patterns, regression tests.

### Aggregator Agent
Merges duplicate findings, prioritizes by severity, contextualizes (test files = lower severity), writes executive summary.

## Dashboard

The Next.js dashboard (`/frontend`) provides:

- Review history with filtering and search
- Detailed findings grouped by file
- Severity and agent filters
- Expandable finding cards with code snippets and suggestions
- Agent performance summaries
- One-click manual review trigger

## Deployment

### Render / Railway / Fly.io

1. Connect repository
2. Set environment variables
3. Deploy with `Dockerfile`
4. Configure webhook URL: `https://your-domain/webhook/github`

### Kubernetes (Helm)

```bash
# Coming: helm/charts/codereview-agent
```

## Development

```bash
# Run tests
poetry run pytest

# Lint
poetry run ruff check .
poetry run ruff format --check .

# Type check
poetry run mypy app/

# Pre-commit
poetry run pre-commit install
```

## Project Structure

```
codereview-agent/
├── app/
│   ├── agents/           # Specialist + aggregator agents
│   ├── api.py            # FastAPI app + routes
│   ├── config.py         # Pydantic Settings
│   ├── github/           # GitHub client + webhooks
│   ├── main.py           # Review queue + worker
│   └── schemas.py        # Pydantic models
├── frontend/             # Next.js 14 dashboard
├── tests/                # Pytest suite
├── .github/workflows/    # CI/CD
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## License

MIT