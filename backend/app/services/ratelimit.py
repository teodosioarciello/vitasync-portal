import logging

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None


def _client_instance():
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _client


def check_rate_limit(key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
    """
    Ritorna (allowed, remaining, retry_after_seconds).
    Fail-open: se Redis non risponde, consente la richiesta e logga warning.
    In produzione valutare fail-closed per gli endpoint critici.
    """
    try:
        r = _client_instance()
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = pipe.execute()
        count = int(count)
        if ttl is None or int(ttl) < 0:
            r.expire(key, window_seconds)
            ttl = window_seconds
        ttl = int(ttl)
        allowed = count <= limit
        remaining = max(0, limit - count)
        retry_after = ttl if not allowed else 0
        return allowed, remaining, retry_after
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rate limiter Redis non disponibile, fail-open: %s", exc)
        return True, limit, 0