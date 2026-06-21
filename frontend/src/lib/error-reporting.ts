/**
 * Lightweight error reporting hook.
 * Drop in a real provider (Sentry, Datadog, etc.) by implementing the
 * same shape and calling it here.
 */
export function reportError(error: unknown, context: Record<string, unknown> = {}) {
  if (typeof window === "undefined") return;
  console.error("[ErrorBoundary]", error, context);
  // TODO: forward to your error monitoring service, e.g.:
  // Sentry.captureException(error, { extra: context });
}
