import logging
import os
import time
from collections import defaultdict

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types
from upstash_redis.asyncio import Redis

logger = logging.getLogger(__name__)


class UpstashRateLimitPlugin(BasePlugin):
    """Distributed rate limiting plugin for ADK agents using Upstash Redis.

    Limits LLM invocations per user within a rolling or fixed time window.
    If Upstash credentials are not set, it gracefully falls back to in-memory
    tracking (suitable for local dev / testing).
    """

    def __init__(
        self,
        name: str = "upstash_rate_limiter",
        max_requests: int = 5,
        window_seconds: int = 60,
        url: str | None = None,
        token: str | None = None,
    ):
        super().__init__(name=name)
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        redis_url = url or os.getenv("UPSTASH_REDIS_REST_URL")
        redis_token = token or os.getenv("UPSTASH_REDIS_REST_TOKEN")

        if redis_url and redis_token:
            self.redis = Redis(url=redis_url, token=redis_token)
            logger.info("UpstashRateLimitPlugin initialized with Upstash Redis.")
        else:
            self.redis = None
            self._in_memory_requests: dict[str, list[float]] = defaultdict(list)
            logger.warning(
                "Upstash credentials not found (UPSTASH_REDIS_REST_URL / UPSTASH_REDIS_REST_TOKEN). "
                "Falling back to local in-memory rate limiting."
            )

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest
    ) -> LlmResponse | None:
        user_id = callback_context.session.user_id or "anonymous"

        if self.redis is not None:
            return await self._check_rate_limit_redis(user_id)
        else:
            return self._check_rate_limit_memory(user_id)

    async def _check_rate_limit_redis(self, user_id: str) -> LlmResponse | None:
        key = f"ratelimit:{user_id}"
        try:
            current_count = await self.redis.incr(key)
            if current_count == 1:
                await self.redis.expire(key, self.window_seconds)

            if current_count > self.max_requests:
                ttl = await self.redis.ttl(key)
                remaining_time = ttl if ttl and ttl > 0 else self.window_seconds
                return self._build_rate_limit_response(remaining_time)
        except Exception as e:
            # Fail-open policy on network errors so user conversation is not broken
            logger.error(f"Error checking rate limit in Upstash Redis: {e}")

        return None

    def _check_rate_limit_memory(self, user_id: str) -> LlmResponse | None:
        now = time.time()
        valid_timestamps = [
            ts
            for ts in self._in_memory_requests[user_id]
            if now - ts < self.window_seconds
        ]
        self._in_memory_requests[user_id] = valid_timestamps

        if len(valid_timestamps) >= self.max_requests:
            oldest_ts = valid_timestamps[0]
            remaining_time = int(self.window_seconds - (now - oldest_ts)) + 1
            return self._build_rate_limit_response(remaining_time)

        self._in_memory_requests[user_id].append(now)
        return None

    def _build_rate_limit_response(self, remaining_time: int) -> LlmResponse:
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_text(
                        text=(
                            f"⏳ Has superado el límite de {self.max_requests} mensajes por minuto. "
                            f"Por favor espera {remaining_time} segundos antes de enviar otro mensaje."
                        )
                    )
                ],
            )
        )
