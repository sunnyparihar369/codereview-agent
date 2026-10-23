"""Tests for agent base functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.base import AgentRegistry, BaseAgent
from app.schemas import AgentName, AgentResult, Finding, FindingCategory, PRContext, Severity


class MockAgent(BaseAgent):
    """Test agent implementation."""

    @property
    def system_prompt(self) -> str:
        return "Test system prompt"

    @property
    def human_prompt_template(self) -> str:
        return "Test human prompt: {context}"


@pytest.fixture
def mock_models():
    """Create mock LLM models."""
    model_simple = AsyncMock()
    model_simple.model_name = "test-simple"
    model_simple.ainvoke = AsyncMock()

    model_complex = AsyncMock()
    model_complex.model_name = "test-complex"
    model_complex.ainvoke = AsyncMock()

    return {"simple": model_simple, "complex": model_complex}


@pytest.fixture
def sample_context():
    """Create sample PR context."""
    return PRContext(
        pr_id="github:owner/repo#123",
        provider="github",
        repository=MagicMock(full_name="owner/repo"),
        pull_request=MagicMock(number=123, title="Test PR", body="Description"),
        files=[],
    )


class TestBaseAgent:
    """Tests for BaseAgent."""

    def test_model_selection_simple(self, mock_models, sample_context):
        """Test simple model selected for small PRs."""
        agent = MockAgent(AgentName.SECURITY, mock_models["simple"], mock_models["complex"], FindingCategory.SECURITY)
        sample_context.files = [
            MagicMock(additions=10, deletions=5),
            MagicMock(additions=5, deletions=2),
        ]
        model = agent._select_model(sample_context)
        assert model == mock_models["simple"]

    def test_model_selection_complex(self, mock_models, sample_context):
        """Test complex model selected for large PRs."""
        agent = MockAgent(AgentName.SECURITY, mock_models["simple"], mock_models["complex"], FindingCategory.SECURITY)
        sample_context.files = [
            MagicMock(additions=300, deletions=200),
            MagicMock(additions=100, deletions=50),
        ]
        model = agent._select_model(sample_context)
        assert model == mock_models["complex"]

    def test_model_selection_many_files(self, mock_models, sample_context):
        """Test complex model selected for many files."""
        agent = MockAgent(AgentName.SECURITY, mock_models["simple"], mock_models["complex"], FindingCategory.SECURITY)
        sample_context.files = [MagicMock(additions=10, deletions=5) for _ in range(15)]
        model = agent._select_model(sample_context)
        assert model == mock_models["complex"]

    @pytest.mark.asyncio
    async def test_run_success(self, mock_models, sample_context):
        """Test successful agent run."""
        agent = MockAgent(AgentName.SECURITY, mock_models["simple"], mock_models["complex"], FindingCategory.SECURITY)

        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = '[{"severity": "high", "title": "Test", "description": "Desc", "filename": "test.py", "line_start": 10, "suggestion": "Fix it", "rule_id": "RULE-1", "confidence": 0.9}]'
        mock_models["simple"].ainvoke.return_value = mock_response

        result = await agent.run(sample_context)

        assert isinstance(result, AgentResult)
        assert result.agent == AgentName.SECURITY
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.HIGH
        assert result.processing_time_ms > 0
        assert result.tokens_used > 0

    @pytest.mark.asyncio
    async def test_run_invalid_json_fallback(self, mock_models, sample_context):
        """Test fallback when LLM returns invalid JSON."""
        agent = MockAgent(AgentName.SECURITY, mock_models["simple"], mock_models["complex"], FindingCategory.SECURITY)

        mock_response = MagicMock()
        mock_response.content = "This is not JSON at all"
        mock_models["simple"].ainvoke.return_value = mock_response

        result = await agent.run(sample_context)

        assert isinstance(result, AgentResult)
        assert len(result.findings) == 1
        assert result.findings[0].severity == Severity.INFO
        assert "not JSON" in result.findings[0].description

    @pytest.mark.asyncio
    async def test_run_llm_error(self, mock_models, sample_context):
        """Test error handling when LLM call fails."""
        agent = MockAgent(AgentName.SECURITY, mock_models["simple"], mock_models["complex"], FindingCategory.SECURITY)
        mock_models["simple"].ainvoke.side_effect = Exception("API Error")

        result = await agent.run(sample_context)

        assert isinstance(result, AgentResult)
        assert len(result.findings) == 0
        assert len(result.errors) == 1
        assert "API Error" in result.errors[0]


class TestAgentRegistry:
    """Tests for AgentRegistry."""

    def test_register_and_get(self, mock_models):
        """Test agent registration and retrieval."""
        registry = AgentRegistry()
        agent = MockAgent(AgentName.SECURITY, mock_models["simple"], mock_models["complex"], FindingCategory.SECURITY)

        registry.register(agent)
        retrieved = registry.get(AgentName.SECURITY)

        assert retrieved is agent

    def test_get_enabled(self, mock_models):
        """Test getting enabled agents based on settings."""
        registry = AgentRegistry()

        # Register all agents
        for name in [AgentName.SECURITY, AgentName.PERFORMANCE, AgentName.STYLE]:
            agent = MockAgent(name, mock_models["simple"], mock_models["complex"], FindingCategory.SECURITY)
            registry.register(agent)

        # Mock settings with some disabled
        class MockSettings:
            enable_security_agent = True
            enable_performance_agent = False
            enable_style_agent = True
            enable_architecture_agent = False
            enable_tests_agent = False

        enabled = registry.get_enabled(MockSettings())
        assert len(enabled) == 2
        assert enabled[0].name == AgentName.SECURITY
        assert enabled[1].name == AgentName.STYLE