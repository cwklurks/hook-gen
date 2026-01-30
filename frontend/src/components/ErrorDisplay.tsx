"use client";

import { motion, AnimatePresence } from "framer-motion";
import { AlertCircle, RefreshCw, X, Clock } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiErrorResponse, getErrorInfo, UserErrorInfo } from "@/utils/errors";

interface ErrorDisplayProps {
  error: ApiErrorResponse | string | null;
  onDismiss?: () => void;
  onRetry?: () => void;
  retryCountdown?: number | null;
  className?: string;
}

export default function ErrorDisplay({
  error,
  onDismiss,
  onRetry,
  retryCountdown,
  className = "",
}: ErrorDisplayProps) {
  const [countdown, setCountdown] = useState<number | null>(retryCountdown ?? null);
  const [prevRetryCountdown, setPrevRetryCountdown] = useState(retryCountdown);

  // React-approved derived state pattern (not in useEffect)
  if (retryCountdown !== prevRetryCountdown) {
    setPrevRetryCountdown(retryCountdown);
    setCountdown(retryCountdown ?? null);
  }

  useEffect(() => {
    if (countdown === null || countdown <= 0) return;

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev === null || prev <= 1) {
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [countdown]);

  if (!error) return null;

  // Resolve error info
  let errorInfo: UserErrorInfo;
  let isRetryable = false;

  if (typeof error === "string") {
    errorInfo = {
      title: "Error",
      message: error,
      retryable: false,
    };
  } else {
    errorInfo = getErrorInfo(error.error_code);
    isRetryable = error.retryable;

    // Override message if backend provided a specific one
    if (error.message && error.message !== errorInfo.message) {
      errorInfo.message = error.message;
    }
  }

  const showRetry = isRetryable && onRetry;
  const isCountingDown = countdown !== null && countdown > 0;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className={`relative overflow-hidden rounded-lg border border-red-500/30 bg-red-500/10 p-4 ${className}`}
      >
        {/* Background glow */}
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-red-500/5 to-transparent" />

        <div className="relative flex gap-3">
          {/* Icon */}
          <div className="flex-shrink-0">
            <AlertCircle className="h-5 w-5 text-red-400" />
          </div>

          {/* Content */}
          <div className="flex-1 space-y-1">
            <p className="text-sm font-medium text-red-300">{errorInfo.title}</p>
            <p className="text-sm text-red-200/80">{errorInfo.message}</p>

            {errorInfo.suggestion && (
              <p className="text-xs text-red-200/60">{errorInfo.suggestion}</p>
            )}

            {/* Retry countdown */}
            {isCountingDown && (
              <div className="flex items-center gap-2 pt-2">
                <Clock className="h-3 w-3 text-red-300/60" />
                <span className="text-xs text-red-300/60">
                  Retry available in {countdown}s
                </span>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex flex-shrink-0 items-start gap-2">
            {showRetry && (
              <button
                onClick={onRetry}
                disabled={isCountingDown}
                className="rounded-md p-1.5 text-red-300 transition-colors hover:bg-red-500/20 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label="Retry"
              >
                <RefreshCw
                  className={`h-4 w-4 ${isCountingDown ? "" : "hover:animate-spin"}`}
                />
              </button>
            )}

            {onDismiss && (
              <button
                onClick={onDismiss}
                className="rounded-md p-1.5 text-red-300 transition-colors hover:bg-red-500/20 hover:text-red-200"
                aria-label="Dismiss error"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

/**
 * Retry indicator shown during retry attempts.
 */
export function RetryIndicator({
  attempt,
  maxAttempts,
  retryAfterMs,
  className = "",
}: {
  attempt: number;
  maxAttempts: number;
  retryAfterMs: number | null;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={`flex items-center gap-2 text-sm text-amber-400 ${className}`}
    >
      <RefreshCw className="h-4 w-4 animate-spin" />
      <span>
        Retrying... (attempt {attempt}/{maxAttempts})
        {retryAfterMs !== null && ` in ${Math.ceil(retryAfterMs / 1000)}s`}
      </span>
    </motion.div>
  );
}
