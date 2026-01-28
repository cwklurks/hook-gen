"""Standardized error handling for Hook-Gen API."""

import logging
from enum import Enum
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Standardized error codes for the API."""

    # Validation errors (4xx)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    DURATION_TOO_LONG = "DURATION_TOO_LONG"
    EMPTY_FILE = "EMPTY_FILE"
    INVALID_FILENAME = "INVALID_FILENAME"

    # Processing errors
    PROCESSING_TIMEOUT = "PROCESSING_TIMEOUT"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"
    GENERATION_FAILED = "GENERATION_FAILED"

    # Rate limiting
    RATE_LIMITED = "RATE_LIMITED"

    # Server errors
    INTERNAL_ERROR = "INTERNAL_ERROR"

    # Resource errors
    NOT_FOUND = "NOT_FOUND"


class ErrorConfig:
    """Configuration for each error code."""

    _configs: dict[ErrorCode, dict] = {
        ErrorCode.VALIDATION_ERROR: {
            "status_code": 400,
            "message": "Invalid request data.",
            "retryable": False,
        },
        ErrorCode.UNSUPPORTED_FORMAT: {
            "status_code": 400,
            "message": (
                "Unsupported audio format. Supported formats: WAV, MP3, FLAC, OGG, M4A, AAC."
            ),
            "retryable": False,
        },
        ErrorCode.FILE_TOO_LARGE: {
            "status_code": 413,
            "message": (
                "File exceeds 20MB limit. For best results, "
                "trim your loop to 8-16 bars before uploading."
            ),
            "retryable": False,
        },
        ErrorCode.DURATION_TOO_LONG: {
            "status_code": 422,
            "message": (
                "Audio duration exceeds 30 seconds. "
                "Please trim your loop to 8-16 bars for optimal analysis."
            ),
            "retryable": False,
        },
        ErrorCode.EMPTY_FILE: {
            "status_code": 400,
            "message": "The uploaded file is empty.",
            "retryable": False,
        },
        ErrorCode.INVALID_FILENAME: {
            "status_code": 400,
            "message": "Invalid filename provided.",
            "retryable": False,
        },
        ErrorCode.PROCESSING_TIMEOUT: {
            "status_code": 408,
            "message": "Audio processing timed out. Try a shorter or simpler audio file.",
            "retryable": True,
        },
        ErrorCode.ANALYSIS_FAILED: {
            "status_code": 422,
            "message": (
                "Failed to analyze the audio file. "
                "The file may be corrupted or in an unsupported format."
            ),
            "retryable": True,
        },
        ErrorCode.GENERATION_FAILED: {
            "status_code": 500,
            "message": "Failed to generate hooks. Please try again.",
            "retryable": True,
        },
        ErrorCode.RATE_LIMITED: {
            "status_code": 429,
            "message": "Rate limit exceeded. Please try again later.",
            "retryable": True,
        },
        ErrorCode.INTERNAL_ERROR: {
            "status_code": 500,
            "message": "An internal server error occurred.",
            "retryable": True,
        },
        ErrorCode.NOT_FOUND: {
            "status_code": 404,
            "message": "The requested resource was not found.",
            "retryable": False,
        },
    }

    @classmethod
    def get(cls, code: ErrorCode) -> dict:
        """Get configuration for an error code."""
        return cls._configs.get(code, cls._configs[ErrorCode.INTERNAL_ERROR])


class ErrorResponse(BaseModel):
    """Standardized error response model."""

    error_code: str
    message: str
    details: Optional[dict] = None
    retry_after: Optional[int] = None
    retryable: bool = False


def create_error_response(
    code: ErrorCode,
    message: Optional[str] = None,
    details: Optional[dict] = None,
    retry_after: Optional[int] = None,
    log_level: str = "warning",
) -> HTTPException:
    """
    Create a standardized HTTPException with error response body.

    Args:
        code: The error code from ErrorCode enum
        message: Optional custom message (overrides default)
        details: Optional additional details dict
        retry_after: Optional retry-after seconds (for rate limiting)
        log_level: Log level - "error" for server errors, "warning" for client errors

    Returns:
        HTTPException with standardized error body
    """
    config = ErrorConfig.get(code)

    error_response = ErrorResponse(
        error_code=code.value,
        message=message or config["message"],
        details=details,
        retry_after=retry_after,
        retryable=config.get("retryable", False),
    )

    # Log based on severity
    log_message = f"{code.value}: {error_response.message}"
    if details:
        log_message += f" | Details: {details}"

    if log_level == "error" or config["status_code"] >= 500:
        logger.error(log_message)
    else:
        logger.warning(log_message)

    headers = {}
    if retry_after:
        headers["Retry-After"] = str(retry_after)

    return HTTPException(
        status_code=config["status_code"],
        detail=error_response.model_dump(),
        headers=headers if headers else None,
    )


def create_sse_error(
    code: ErrorCode,
    message: Optional[str] = None,
    details: Optional[dict] = None,
) -> dict:
    """
    Create error data for SSE streaming endpoints.

    Returns a dict suitable for use with sse_event("error", ...).
    """
    config = ErrorConfig.get(code)

    return {
        "error_code": code.value,
        "detail": message or config["message"],
        "details": details,
        "retryable": config.get("retryable", False),
    }
