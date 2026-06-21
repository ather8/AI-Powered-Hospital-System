/**
 * AiLoadingSkeleton — loading placeholder for AI result areas.
 *
 * Shows animated skeleton lines while an AI API call is in-flight so the
 * user sees immediate feedback instead of a static spinner or blank space.
 * Accepts an optional `lines` prop to match the expected result height.
 */

import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface Props {
  /** Number of skeleton lines to render. Default: 4 */
  lines?: number;
  /** Additional class names for the wrapper */
  className?: string;
  /** Short label shown above the skeleton (e.g. "Generating summary…") */
  label?: string;
}

export function AiLoadingSkeleton({ lines = 4, className, label }: Props) {
  return (
    <div className={cn("space-y-2", className)} role="status" aria-busy="true">
      {label && (
        <p className="text-xs text-muted-foreground animate-pulse">{label}</p>
      )}
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          // Last line is shorter to look like a natural paragraph ending
          className={cn("h-4", i === lines - 1 ? "w-3/4" : "w-full")}
        />
      ))}
    </div>
  );
}

/**
 * AiUnavailableBanner — inline banner shown when an AI endpoint returns
 * ``status: "disabled"`` (e.g. missing FAISS index, no API key).
 * Distinct from AiErrorBoundary (which catches JS render errors); this
 * handles graceful API-level degradation signalled by the backend.
 */
interface BannerProps {
  detail?: string;
  className?: string;
}

export function AiUnavailableBanner({ detail, className }: BannerProps) {
  return (
    <div
      className={cn(
        "rounded-md border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950 p-4 text-sm",
        className
      )}
      role="alert"
    >
      <p className="font-medium text-amber-800 dark:text-amber-200">
        AI feature unavailable
      </p>
      {detail ? (
        <p className="mt-1 text-amber-700 dark:text-amber-300 text-xs">{detail}</p>
      ) : (
        <p className="mt-1 text-amber-700 dark:text-amber-300 text-xs">
          Check that an AI provider key is configured and the server is
          running. See <code>backend/.env.example</code> for setup instructions.
        </p>
      )}
    </div>
  );
}
