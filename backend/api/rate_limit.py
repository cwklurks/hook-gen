import logging
import os

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from api.errors import ErrorCode, ErrorResponse

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Extract client IP from X-Forwarded-For or direct connection."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


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
        f"Rate limit exceeded: client_ip={client_ip}, endpoint={request.url.path}, limit={exc.detail}"
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
