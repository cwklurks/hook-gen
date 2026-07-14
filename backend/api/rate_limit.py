import logging
import os
from ipaddress import ip_address

from api.errors import ErrorCode, ErrorResponse
from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Return a rate-limit identity without trusting caller-controlled headers.

    ``X-Forwarded-For`` is ignored by default. Deployments behind a network-
    restricted reverse proxy may set ``TRUSTED_PROXY_HOPS`` to the exact number
    of trusted proxy hops. Selecting from the right prevents a client from
    bypassing limits by prepending arbitrary addresses.
    """
    remote_address = str(get_remote_address(request))

    try:
        trusted_proxy_hops = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))
    except ValueError:
        logger.warning("Ignoring invalid TRUSTED_PROXY_HOPS value")
        return remote_address

    if trusted_proxy_hops <= 0:
        return remote_address

    forwarded_for = request.headers.get("X-Forwarded-For")
    if not forwarded_for:
        return remote_address

    addresses = [value.strip() for value in forwarded_for.split(",") if value.strip()]
    if len(addresses) < trusted_proxy_hops:
        return remote_address

    candidate = addresses[-trusted_proxy_hops]
    try:
        return str(ip_address(candidate))
    except ValueError:
        logger.warning("Ignoring invalid client address from X-Forwarded-For")
        return remote_address


def create_limiter() -> Limiter:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        logger.info("Rate limiter using Redis backend")
    else:
        logger.info("Rate limiter using in-memory backend")
    return Limiter(key_func=get_client_ip, storage_uri=redis_url)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    client_ip = get_client_ip(request)
    logger.warning(
        f"Rate limit exceeded: client_ip={client_ip}, "
        f"endpoint={request.url.path}, limit={exc.detail}"
    )

    error_response = ErrorResponse(
        error_code=ErrorCode.RATE_LIMITED.value,
        message="Rate limit exceeded. Please try again later.",
        details={"limit": str(exc.detail)},
        retry_after=60,
        retryable=True,
    )

    response = JSONResponse(
        status_code=429,
        content=error_response.model_dump(),
    )
    response.headers["Retry-After"] = "60"
    return response


limiter = create_limiter()
ANALYZE_RATE_LIMIT = "10/minute"
GENERATE_RATE_LIMIT = "30/minute"
EXPORT_RATE_LIMIT = "30/minute"
SESSION_SAVE_RATE_LIMIT = "20/minute"
