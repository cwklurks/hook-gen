/**
 * Error handling utilities for Hook-Gen frontend.
 */

/**
 * Backend error response structure.
 */
export interface ApiErrorResponse {
  error_code: string;
  message: string;
  details?: Record<string, unknown>;
  retry_after?: number;
  retryable: boolean;
}

/**
 * Error codes from the backend.
 */
export enum ErrorCode {
  VALIDATION_ERROR = "VALIDATION_ERROR",
  UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT",
  FILE_TOO_LARGE = "FILE_TOO_LARGE",
  DURATION_TOO_LONG = "DURATION_TOO_LONG",
  EMPTY_FILE = "EMPTY_FILE",
  INVALID_FILENAME = "INVALID_FILENAME",
  PROCESSING_TIMEOUT = "PROCESSING_TIMEOUT",
  ANALYSIS_FAILED = "ANALYSIS_FAILED",
  GENERATION_FAILED = "GENERATION_FAILED",
  RATE_LIMITED = "RATE_LIMITED",
  INTERNAL_ERROR = "INTERNAL_ERROR",
  NOT_FOUND = "NOT_FOUND",
}

/**
 * User-friendly error info with suggestions.
 */
export interface UserErrorInfo {
  title: string;
  message: string;
  suggestion?: string;
  retryable: boolean;
}

/**
 * Map error codes to user-friendly messages and suggestions.
 */
export function getErrorInfo(errorCode: string): UserErrorInfo {
  const errorMap: Record<string, UserErrorInfo> = {
    [ErrorCode.UNSUPPORTED_FORMAT]: {
      title: "Unsupported Format",
      message: "This audio format is not supported.",
      suggestion: "Please upload a WAV, MP3, FLAC, OGG, M4A, or AAC file.",
      retryable: false,
    },
    [ErrorCode.FILE_TOO_LARGE]: {
      title: "File Too Large",
      message: "The file exceeds the 20MB size limit.",
      suggestion: "Try trimming your audio to 8-16 bars before uploading.",
      retryable: false,
    },
    [ErrorCode.DURATION_TOO_LONG]: {
      title: "Audio Too Long",
      message: "Audio duration exceeds 30 seconds.",
      suggestion: "Trim your loop to 8-16 bars for best results.",
      retryable: false,
    },
    [ErrorCode.EMPTY_FILE]: {
      title: "Empty File",
      message: "The uploaded file appears to be empty.",
      suggestion: "Please select a valid audio file.",
      retryable: false,
    },
    [ErrorCode.PROCESSING_TIMEOUT]: {
      title: "Processing Timeout",
      message: "Audio analysis took too long.",
      suggestion: "Try a shorter or less complex audio file.",
      retryable: true,
    },
    [ErrorCode.ANALYSIS_FAILED]: {
      title: "Analysis Failed",
      message: "Could not analyze the audio file.",
      suggestion: "The file may be corrupted. Try a different audio file.",
      retryable: true,
    },
    [ErrorCode.GENERATION_FAILED]: {
      title: "Generation Failed",
      message: "Failed to generate hook variations.",
      suggestion: "Please try again.",
      retryable: true,
    },
    [ErrorCode.RATE_LIMITED]: {
      title: "Too Many Requests",
      message: "You've made too many requests.",
      suggestion: "Please wait a moment before trying again.",
      retryable: true,
    },
    [ErrorCode.INTERNAL_ERROR]: {
      title: "Server Error",
      message: "Something went wrong on our end.",
      suggestion: "Please try again later.",
      retryable: true,
    },
    [ErrorCode.NOT_FOUND]: {
      title: "Not Found",
      message: "The requested resource was not found.",
      suggestion: undefined,
      retryable: false,
    },
    [ErrorCode.VALIDATION_ERROR]: {
      title: "Invalid Request",
      message: "The request contained invalid data.",
      suggestion: undefined,
      retryable: false,
    },
    [ErrorCode.INVALID_FILENAME]: {
      title: "Invalid Filename",
      message: "The filename is not valid.",
      suggestion: undefined,
      retryable: false,
    },
  };

  return (
    errorMap[errorCode] || {
      title: "Error",
      message: "An unexpected error occurred.",
      suggestion: "Please try again.",
      retryable: true,
    }
  );
}

/**
 * Parse an error response from the backend.
 * Handles both new structured errors and legacy format.
 */
export function parseErrorResponse(data: unknown): ApiErrorResponse | null {
  if (!data || typeof data !== "object") {
    return null;
  }

  const obj = data as Record<string, unknown>;

  // New structured error format
  if ("error_code" in obj && typeof obj.error_code === "string") {
    return {
      error_code: obj.error_code,
      message: typeof obj.message === "string" ? obj.message : "An error occurred",
      details: typeof obj.details === "object" ? (obj.details as Record<string, unknown>) : undefined,
      retry_after: typeof obj.retry_after === "number" ? obj.retry_after : undefined,
      retryable: typeof obj.retryable === "boolean" ? obj.retryable : false,
    };
  }

  // Legacy format: { detail: string } or { detail: { ... } }
  if ("detail" in obj) {
    const detail = obj.detail;

    // detail might be the structured error itself
    if (typeof detail === "object" && detail !== null && "error_code" in (detail as Record<string, unknown>)) {
      const detailObj = detail as Record<string, unknown>;
      return {
        error_code: detailObj.error_code as string,
        message: typeof detailObj.message === "string" ? detailObj.message : "An error occurred",
        details: typeof detailObj.details === "object" ? (detailObj.details as Record<string, unknown>) : undefined,
        retry_after: typeof detailObj.retry_after === "number" ? detailObj.retry_after : undefined,
        retryable: typeof detailObj.retryable === "boolean" ? detailObj.retryable : false,
      };
    }

    // Plain string detail - convert to generic error
    if (typeof detail === "string") {
      return {
        error_code: ErrorCode.INTERNAL_ERROR,
        message: detail,
        retryable: true,
      };
    }
  }

  return null;
}

/**
 * Extract a user-displayable message from any error response.
 */
export function getDisplayMessage(
  responseData: unknown,
  fallbackMessage = "An unexpected error occurred"
): string {
  const parsed = parseErrorResponse(responseData);
  if (parsed) {
    return parsed.message;
  }
  return fallbackMessage;
}
