"""
Auralis LLM Service
Abstraction layer supporting OpenAI API and local Ollama models.
Factory pattern allows seamless switching via LLM_PROVIDER config.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from app.core.config import settings
from app.core.logging import logger


class LLMService(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response from the LLM given a list of messages."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the LLM service is reachable."""
        pass


class OpenAILLMService(LLMService):
    """OpenAI API adapter (GPT-4o, GPT-3.5-turbo, etc.)."""

    def __init__(self):
        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            self.model = settings.OPENAI_MODEL
            logger.info(f"OpenAI LLM Service ready | Model: {self.model}")
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            logger.info(f"OpenAI response | Tokens: {response.usage.total_tokens}")
            return content
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise

    def is_available(self) -> bool:
        return bool(settings.OPENAI_API_KEY)


class OllamaLLMService(LLMService):
    """Ollama local LLM adapter (Llama3, Mistral, etc.) – no API key required."""

    def __init__(self):
        try:
            import ollama
            self.ollama = ollama
            self.model = settings.OLLAMA_MODEL
            self.base_url = settings.OLLAMA_BASE_URL
            logger.info(f"Ollama LLM Service ready | Model: {self.model} | URL: {self.base_url}")
        except ImportError:
            raise RuntimeError("ollama package not installed. Run: pip install ollama")

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.ollama.chat(
                    model=self.model,
                    messages=messages,
                    options={"temperature": temperature, "num_predict": max_tokens},
                ),
            )
            content = response["message"]["content"]
            logger.info(f"Ollama response generated | Model: {self.model}")
            return content
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise

    def is_available(self) -> bool:
        try:
            import requests
            resp = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False


class MockLLMService(LLMService):
    """
    Fallback mock LLM for demo/testing when no API key or Ollama is available.
    Returns intelligent-looking canned responses based on keywords.
    """

    DEMO_RESPONSES = [
        "I'm Auralis, your AI assistant! I can answer questions using knowledge from my knowledge base via Retrieval-Augmented Generation (RAG). To get real AI responses, please configure your OPENAI_API_KEY in the .env file or set up Ollama locally.",
        "Great question! Based on context-aware processing, I would analyze your query semantically and retrieve the most relevant information from my knowledge base before generating a response.",
        "This is a demo response from Auralis. The RAG pipeline is active and has retrieved context from the knowledge base. In production mode with an OpenAI API key, I would provide a comprehensive, contextually grounded answer here.",
        "Auralis is designed to provide accurate, context-aware responses. My architecture includes: (1) Vector-based knowledge retrieval, (2) Multi-turn context management, and (3) Prompt-engineered LLM generation. Configure LLM_PROVIDER in .env to activate full AI capabilities.",
    ]

    _response_index = 0

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        import asyncio
        await asyncio.sleep(0.5)  # Simulate latency
        user_msg = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        response = self.DEMO_RESPONSES[MockLLMService._response_index % len(self.DEMO_RESPONSES)]
        MockLLMService._response_index += 1
        logger.warning("MockLLMService used – configure OpenAI API key or Ollama for real responses")
        return f"[DEMO MODE] {response}"

    def is_available(self) -> bool:
        return True


def get_llm_service() -> LLMService:
    """
    Factory function: returns the appropriate LLM service based on config.
    Falls back gracefully: OpenAI → Ollama → Mock.
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            logger.warning("LLM_PROVIDER=openai but OPENAI_API_KEY not set – falling back to Ollama")
            provider = "ollama"
        else:
            return OpenAILLMService()

    if provider == "ollama":
        try:
            service = OllamaLLMService()
        except (RuntimeError, ImportError):
            logger.warning("Ollama package not installed - falling back to Mock LLM (demo mode)")
            return MockLLMService()
        if not service.is_available():
            logger.warning("Ollama not reachable - falling back to Mock LLM (demo mode)")
            return MockLLMService()
        return service

    logger.warning(f"Unknown LLM_PROVIDER '{provider}' - using Mock LLM (demo mode)")
    return MockLLMService()


# Singleton LLM service
_llm_service: Optional[LLMService] = None


def llm_service() -> LLMService:
    """Dependency-injectable singleton LLM service."""
    global _llm_service
    if _llm_service is None:
        _llm_service = get_llm_service()
    return _llm_service
