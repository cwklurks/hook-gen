/**
 * Fetch wrapper with retry logic and exponential backoff.
 */

import { parseErrorResponse } from "./errors";

export interface RetryConfig {
  maxRetries: number;
  initialDelayMs: number;
  maxDelayMs: number;
  retryableStatuses: number[];
}

export interface RetryState {
  attempt: number;
  isRetrying: boolean;
  retryAfterMs: number | null;
}

export interface FetchWithRetryOptions extends RequestInit {
  retryConfig?: Partial<RetryConfig>;
  onRetryStateChange?: (state: RetryState) => void;
  abortSignal?: AbortSignal;
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  initialDelayMs: 1000,
  maxDelayMs: 10000,
  retryableStatuses: [429, 502, 503, 504],
};

/**
 * Calculate delay with exponential backoff.
 */
function calculateDelay(
  attempt: number,
  config: RetryConfig,
  retryAfterHeader?: string | null
): number {
  // If Retry-After header is present, use it
  if (retryAfterHeader) {
    const retryAfterSeconds = parseInt(retryAfterHeader, 10);
    if (!isNaN(retryAfterSeconds)) {
      return retryAfterSeconds * 1000;
    }
  }

  // Exponential backoff: initialDelay * 2^attempt
  const exponentialDelay = config.initialDelayMs * Math.pow(2, attempt);

  // Add jitter (10-30% random variation)
  const jitter = exponentialDelay * (0.1 + Math.random() * 0.2);

  return Math.min(exponentialDelay + jitter, config.maxDelayMs);
}

/**
 * Sleep for a specified duration, respecting abort signal.
 */
async function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(resolve, ms);

    if (signal) {
      if (signal.aborted) {
        clearTimeout(timeout);
        reject(new DOMException("Aborted", "AbortError"));
        return;
      }

      const abortHandler = () => {
        clearTimeout(timeout);
        reject(new DOMException("Aborted", "AbortError"));
      };

      signal.addEventListener("abort", abortHandler, { once: true });

      // Clean up listener after timeout resolves
      setTimeout(() => {
        signal.removeEventListener("abort", abortHandler);
      }, ms + 10);
    }
  });
}

/**
 * Determine if a response should be retried.
 */
function shouldRetry(
  response: Response,
  config: RetryConfig,
  responseData?: unknown
): boolean {
  // Check if status code is retryable
  if (config.retryableStatuses.includes(response.status)) {
    return true;
  }

  // Check if backend indicates retryable
  if (responseData) {
    const parsed = parseErrorResponse(responseData);
    if (parsed?.retryable) {
      return true;
    }
  }

  return false;
}

/**
 * Fetch with automatic retry on transient failures.
 */
export async function fetchWithRetry(
  url: string,
  options: FetchWithRetryOptions = {}
): Promise<Response> {
  const { retryConfig, onRetryStateChange, abortSignal, ...fetchOptions } = options;

  const config: RetryConfig = {
    ...DEFAULT_RETRY_CONFIG,
    ...retryConfig,
  };

  let lastError: Error | null = null;
  let lastResponse: Response | null = null;

  for (let attempt = 0; attempt <= config.maxRetries; attempt++) {
    // Notify initial state
    onRetryStateChange?.({
      attempt,
      isRetrying: attempt > 0,
      retryAfterMs: null,
    });

    try {
      // Check if aborted before making request
      if (abortSignal?.aborted) {
        throw new DOMException("Aborted", "AbortError");
      }

      const response = await fetch(url, {
        ...fetchOptions,
        signal: abortSignal,
      });

      // Success - return immediately
      if (response.ok) {
        return response;
      }

      // Clone response to read body for retry decision
      const clonedResponse = response.clone();
      let responseData: unknown;

      try {
        responseData = await clonedResponse.json();
      } catch {
        // Response might not be JSON
        responseData = null;
      }

      // Check if we should retry
      if (attempt < config.maxRetries && shouldRetry(response, config, responseData)) {
        const retryAfterHeader = response.headers.get("Retry-After");
        const delayMs = calculateDelay(attempt, config, retryAfterHeader);

        onRetryStateChange?.({
          attempt: attempt + 1,
          isRetrying: true,
          retryAfterMs: delayMs,
        });

        await sleep(delayMs, abortSignal);
        continue;
      }

      // Not retryable or max retries reached
      lastResponse = response;
      break;
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw error; // Don't retry on abort
      }

      lastError = error instanceof Error ? error : new Error(String(error));

      // Network errors are generally retryable
      if (attempt < config.maxRetries) {
        const delayMs = calculateDelay(attempt, config);

        onRetryStateChange?.({
          attempt: attempt + 1,
          isRetrying: true,
          retryAfterMs: delayMs,
        });

        await sleep(delayMs, abortSignal);
        continue;
      }
    }
  }

  // Final state - no more retries
  onRetryStateChange?.({
    attempt: config.maxRetries,
    isRetrying: false,
    retryAfterMs: null,
  });

  // Return last response or throw last error
  if (lastResponse) {
    return lastResponse;
  }

  throw lastError || new Error("Request failed after retries");
}
