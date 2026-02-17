"""Client pool manager for multi-LLM orchestration."""

import asyncio
import logging
import time
from dataclasses import dataclass

from ultimate_debate.clients.base import BaseAIClient
from ultimate_debate.clients.gemini_client import GeminiClient
from ultimate_debate.clients.openai_client import OpenAIClient

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Health check result for a single AI client.

    Attributes:
        available: True if client passed health check
        latency_ms: Round-trip latency in milliseconds (0 if unavailable)
        model_version: Discovered model version from health check
        error: Error message if unavailable (empty if available)
    """
    available: bool
    latency_ms: float = 0.0
    model_version: str = ""
    error: str = ""


class ClientPool:
    """Manages AI client instances with authentication status tracking.

    Provides graceful degradation: authentication failures don't break workflow.
    """

    def __init__(self) -> None:
        """Initialize empty client pool."""
        self._clients: dict[str, BaseAIClient] = {}
        self._auth_status: dict[str, bool] = {}

    async def initialize(self, models: list[str] | None = None) -> None:
        """Initialize AI clients with authentication.

        Args:
            models: List of model names to initialize. Defaults to ["gpt", "gemini"].

        Note:
            Authentication failures are logged but don't raise exceptions.
            Failed models are marked unavailable in _auth_status.
        """
        if models is None:
            models = ["gpt", "gemini"]

        for model in models:
            try:
                if model == "gpt":
                    client = OpenAIClient("gpt-5.2-codex")
                elif model == "gemini":
                    client = GeminiClient("gemini-2.5-flash")
                else:
                    logger.warning(f"Unsupported model '{model}', skipping")
                    continue

                await client.ensure_authenticated()
                self._clients[model] = client
                self._auth_status[model] = True
                logger.info(f"✓ {model} client initialized")
            except Exception as e:
                logger.warning(f"{model} authentication failed: {e}")
                self._auth_status[model] = False

    async def get_client(self, model: str) -> BaseAIClient | None:
        """Get authenticated client for model.

        Args:
            model: Model name (e.g., "gpt", "gemini")

        Returns:
            BaseAIClient instance if authenticated, None otherwise
        """
        if not self._auth_status.get(model, False):
            return None
        return self._clients.get(model)

    @property
    def available_models(self) -> list[str]:
        """Get list of successfully authenticated models.

        Returns:
            List of model names with auth_status=True
        """
        return [model for model, status in self._auth_status.items() if status]

    async def health_check(self, timeout: float = 30.0) -> dict[str, HealthStatus]:
        """Check health of all registered clients.

        Performs lightweight analyze() call to verify:
        - Authentication is valid
        - API is reachable
        - Model is responsive

        Args:
            timeout: Max seconds to wait for each client (default: 30)

        Returns:
            Dict mapping model name to HealthStatus

        Example:
            >>> pool = ClientPool()
            >>> await pool.initialize()
            >>> health = await pool.health_check()
            >>> if health["gpt"].available:
            ...     print(f"GPT latency: {health['gpt'].latency_ms:.0f}ms")
        """
        results = {}

        for model, client in self._clients.items():
            try:
                start = time.monotonic()
                # Lightweight health check: short analyze call
                response = await asyncio.wait_for(
                    client.analyze(
                        "health check ping",
                        context={"health_check": True}
                    ),
                    timeout=timeout
                )
                latency = (time.monotonic() - start) * 1000

                # Extract model version from response
                model_version = response.get(
                    "model_version",
                    getattr(client, 'discovered_model', client.model_name)
                )

                results[model] = HealthStatus(
                    available=True,
                    latency_ms=latency,
                    model_version=model_version
                )
                logger.info(
                    f"✓ {model} health check passed "
                    f"({latency:.0f}ms, {model_version})"
                )
            except TimeoutError:
                results[model] = HealthStatus(
                    available=False,
                    error=f"Timeout after {timeout}s"
                )
                logger.warning(f"✗ {model} health check timeout")
            except Exception as e:
                results[model] = HealthStatus(
                    available=False,
                    error=str(e)
                )
                logger.warning(f"✗ {model} health check failed: {e}")

        return results

    async def close(self) -> None:
        """Cleanup client pool resources."""
        self._clients.clear()
        self._auth_status.clear()
        logger.info("ClientPool closed")
