from unittest.mock import AsyncMock, MagicMock
import pytest
from app.rate_limiter import UpstashRateLimitPlugin
from google.adk.models.llm_request import LlmRequest


@pytest.mark.asyncio
async def test_in_memory_rate_limiter_blocks_after_limit():
    plugin = UpstashRateLimitPlugin(max_requests=2, window_seconds=60)

    # Mock callback context
    mock_context = MagicMock()
    mock_context.session.user_id = "test_user_1"
    mock_request = MagicMock(spec=LlmRequest)

    # 1st request -> Allowed (None)
    res1 = await plugin.before_model_callback(
        callback_context=mock_context, llm_request=mock_request
    )
    assert res1 is None

    # 2nd request -> Allowed (None)
    res2 = await plugin.before_model_callback(
        callback_context=mock_context, llm_request=mock_request
    )
    assert res2 is None

    # 3rd request -> Blocked (Returns LlmResponse)
    res3 = await plugin.before_model_callback(
        callback_context=mock_context, llm_request=mock_request
    )
    assert res3 is not None
    assert "Has superado el límite" in res3.content.parts[0].text

    # Another user is not affected
    other_user_context = MagicMock()
    other_user_context.session.user_id = "test_user_2"
    res_other = await plugin.before_model_callback(
        callback_context=other_user_context, llm_request=mock_request
    )
    assert res_other is None


@pytest.mark.asyncio
async def test_redis_rate_limiter_flow():
    plugin = UpstashRateLimitPlugin(
        max_requests=2,
        window_seconds=86400,
        url="https://mock.upstash.io",
        token="mock_token",
    )

    # Mock redis client
    mock_redis = AsyncMock()
    plugin.redis = mock_redis

    mock_context = MagicMock()
    mock_context.session.user_id = "user_redis"
    mock_request = MagicMock(spec=LlmRequest)

    # 1st call: count = 1
    mock_redis.incr.return_value = 1
    res1 = await plugin.before_model_callback(
        callback_context=mock_context, llm_request=mock_request
    )
    assert res1 is None
    mock_redis.expire.assert_awaited_once_with("ratelimit:user_redis", 86400)

    # 2nd call: count = 2
    mock_redis.incr.return_value = 2
    res2 = await plugin.before_model_callback(
        callback_context=mock_context, llm_request=mock_request
    )
    assert res2 is None

    # 3rd call: count = 3 -> Exceeded (TTL 7200s -> 2h 0m)
    mock_redis.incr.return_value = 3
    mock_redis.ttl.return_value = 7200
    res3 = await plugin.before_model_callback(
        callback_context=mock_context, llm_request=mock_request
    )
    assert res3 is not None
    assert "límite diario de 2 mensajes" in res3.content.parts[0].text
    assert "2h 0m" in res3.content.parts[0].text
