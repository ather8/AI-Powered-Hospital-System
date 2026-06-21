/**
 * usePagination — lightweight client-side pagination state hook.
 *
 * Tracks `skip` and `limit` and exposes `next` / `prev` / `reset`
 * helpers. Pair with a useQuery that passes { skip, limit } as query
 * params and uses `meta.has_next` / `meta.has_prev` from the response.
 *
 * Example:
 *
 *   const { skip, limit, next, prev, reset } = usePagination();
 *   const { data } = useQuery({
 *     queryKey: ["patients", skip, limit],
 *     queryFn: () => api.get("/patients/", { skip, limit }),
 *   });
 *   // data.meta.total, data.meta.has_next, data.data (the items)
 */
import { useState } from "react";

export interface PaginationState {
  skip: number;
  limit: number;
  next: () => void;
  prev: () => void;
  reset: () => void;
}

export function usePagination(initialLimit = 20): PaginationState {
  const [skip, setSkip] = useState(0);
  const limit = initialLimit;

  return {
    skip,
    limit,
    next: () => setSkip((s) => s + limit),
    prev: () => setSkip((s) => Math.max(0, s - limit)),
    reset: () => setSkip(0),
  };
}
