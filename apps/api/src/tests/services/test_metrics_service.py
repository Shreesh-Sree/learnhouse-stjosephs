import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.services.monitoring.metrics import get_prometheus_metrics


@pytest.mark.asyncio
async def test_get_prometheus_metrics():
    fake_db = MagicMock()
    fake_scalar = MagicMock()
    fake_scalar.scalar.return_value = 1
    fake_db.execute = AsyncMock(return_value=fake_scalar)

    mock_redis = MagicMock()
    mock_redis.ping.return_value = True

    with patch("src.services.monitoring.metrics.get_redis_client", return_value=mock_redis):
        # Reset cache to test generation
        with patch("src.services.monitoring.metrics._CACHED_METRICS", ""):
            metrics_out = await get_prometheus_metrics(fake_db)
            assert "learnhouse_up 1" in metrics_out
            assert "learnhouse_database_healthy 1" in metrics_out
            assert "learnhouse_redis_healthy 1" in metrics_out
            assert "learnhouse_users_total" in metrics_out
            assert "learnhouse_courses_total" in metrics_out
