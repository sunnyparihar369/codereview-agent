"""FastAPI application and routes."""

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langsmith import Client as LangSmithClient
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response

from app.config import get_settings
from app.github.webhook import manual_router, router as webhook_router
from app.main import review_queue
from app.schemas import HealthResponse, ReviewRequest, ReviewResponse

logger = logging.getLogger(__name__)
settings = get_settings()

# Prometheus metrics
REVIEW_REQUESTS = Counter("codereview_review_requests_total", "Total review requests", ["provider", "trigger", "status"])
REVIEW_DURATION = Histogram("codereview_review_duration_seconds", "Review duration in seconds")
REVIEW_FINDINGS = Histogram("codereview_findings_total", "Total findings per review", ["severity"])
LLM_TOKENS = Counter("codereview_llm_tokens_total", "Total LLM tokens used", ["model", "agent"])
LLM_LATENCY = Histogram("codereview_llm_latency_seconds", "LLM call latency", ["model", "agent"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting CodeReview Agent...")

    # Initialize LLM models
    models = await init_llm_models()
    await review_queue.initialize(models)
    await review_queue.start()

    # Initialize LangSmith
    if settings.langsmith_tracing and settings.langsmith_api_key:
        try:
            langsmith_client = LangSmithClient(api_key=settings.langsmith_api_key.get_secret_value())
            app.state.langsmith = langsmith_client
            logger.info("LangSmith tracing enabled")
        except Exception as e:
            logger.warning("Failed to initialize LangSmith: %s", e)

    logger.info("CodeReview Agent started successfully")
    yield

    # Shutdown
    logger.info("Shutting down CodeReview Agent...")
    await review_queue.stop()
    logger.info("CodeReview Agent stopped")


async def init_llm_models() -> dict[str, Any]:
    """Initialize LLM models based on configuration."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    models = {}

    if settings.default_llm_provider == "gemini" and settings.gemini_api_key:
        models["simple"] = ChatGoogleGenerativeAI(
            model=settings.model_simple,
            google_api_key=settings.gemini_api_key.get_secret_value(),
            temperature=0.1,
            max_output_tokens=4096,
        )
        models["complex"] = ChatGoogleGenerativeAI(
            model=settings.model_complex,
            google_api_key=settings.gemini_api_key.get_secret_value(),
            temperature=0.1,
            max_output_tokens=8192,
        )
    elif settings.default_llm_provider == "anthropic" and settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        models["simple"] = ChatAnthropic(
            model=settings.model_simple,
            api_key=settings.anthropic_api_key.get_secret_value(),
            temperature=0.1,
            max_tokens=4096,
        )
        models["complex"] = ChatAnthropic(
            model=settings.model_complex,
            api_key=settings.anthropic_api_key.get_secret_value(),
            temperature=0.1,
            max_tokens=8192,
        )
    elif settings.default_llm_provider == "openai" and settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        models["simple"] = ChatOpenAI(
            model=settings.model_simple,
            api_key=settings.openai_api_key.get_secret_value(),
            temperature=0.1,
            max_tokens=4096,
        )
        models["complex"] = ChatOpenAI(
            model=settings.model_complex,
            api_key=settings.openai_api_key.get_secret_value(),
            temperature=0.1,
            max_tokens=8192,
        )
    else:
        raise ValueError(f"No valid LLM provider configured: {settings.default_llm_provider}")

    return models


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="CodeReview Agent",
        description="Multi-agent automated code review system",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(webhook_router)
    app.include_router(manual_router)

    # Health check
    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        return HealthResponse(
            status="healthy",
            version="0.1.0",
            environment=settings.environment,
            timestamp=__import__("datetime").datetime.utcnow(),
        )

    # Metrics endpoint
    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type="text/plain")

    # Job status endpoints
    @app.get("/api/jobs")
    async def list_jobs(limit: int = 50) -> list[dict]:
        jobs = review_queue.get_all_jobs(limit)
        return [
            {
                "pr_id": j.pr_id,
                "status": j.status.value,
                "trigger": j.trigger,
                "created_at": j.created_at.isoformat(),
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "error": j.error,
                "findings_count": len(j.result.all_findings) if j.result else 0,
            }
            for j in jobs
        ]

    @app.get("/api/jobs/{pr_id}")
    async def get_job(pr_id: str) -> dict:
        job = review_queue.get_job(pr_id)
        if not job:
            return JSONResponse(status_code=404, content={"error": "Job not found"})
        return {
            "pr_id": job.pr_id,
            "status": job.status.value,
            "trigger": job.trigger,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error": job.error,
            "result": job.result.model_dump() if job.result else None,
        }

    # Manual review trigger
    @app.post("/api/review", response_model=ReviewResponse)
    async def trigger_review(request: ReviewRequest) -> ReviewResponse:
        # This is handled by manual_router, but keeping for direct API access
        from app.github.webhook import trigger_manual_review

        response = await trigger_manual_review(request.pr_url, request.provider, request.force)
        REVIEW_REQUESTS.labels(
            provider=request.provider.value, trigger="manual", status="accepted" if response.accepted else "rejected"
        ).inc()
        return ReviewResponse(review_id=response.pr_id or "", status=response.accepted and ReviewStatus.PENDING or ReviewStatus.FAILED, message=response.message)

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

    return app


app = create_app()
