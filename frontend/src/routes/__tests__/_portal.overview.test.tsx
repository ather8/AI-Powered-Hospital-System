/**
 * Tests for src/routes/_portal.overview.tsx, focused on the stat cards'
 * loading and error states -- previously a card with a failed fetch (most
 * notably the "Outstanding balance" card, which sums bills client-side)
 * would either show a stale/misleading "$0.00 / All paid up" or hang on
 * nothing at all, with no way for the patient to tell the request failed.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";

vi.mock("@tanstack/react-router", () => import("@/test/mockRouter"));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { email: "jane@example.com", role: "patient", id: "1" } }),
}));

const mockGet = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { get: (...args: any[]) => mockGet(...args) },
}));

import { Route } from "@/routes/_portal.overview";

const PortalOverview = (Route as any).options.component;

function renderWithQueryClient() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <PortalOverview />
    </QueryClientProvider>,
  );
}

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("PortalOverview stat cards", () => {
  beforeEach(() => {
    mockGet.mockReset();
  });

  it("shows a loading skeleton while bills are still fetching", async () => {
    const apptsDeferred = deferred();
    const billsDeferred = deferred();
    const notifsDeferred = deferred();
    mockGet.mockImplementation((url: string) => {
      if (url.startsWith("/appointments")) return apptsDeferred.promise;
      if (url.startsWith("/billing/me")) return billsDeferred.promise;
      if (url.startsWith("/notifications")) return notifsDeferred.promise;
      throw new Error(`unexpected url ${url}`);
    });

    renderWithQueryClient();

    // Outstanding balance card should not show a dollar value while loading.
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
    expect(screen.queryByText("Couldn't load")).not.toBeInTheDocument();

    // Resolve everything so the test doesn't leave dangling timers/promises.
    apptsDeferred.resolve({ data: [], meta: { total: 0 } });
    billsDeferred.resolve({ data: [], meta: { total: 0 } });
    notifsDeferred.resolve({ count: 0 });
    await waitFor(() => expect(screen.getByText("$0.00")).toBeInTheDocument());
  });

  it("shows an error state on the balance card when the bills request fails, instead of a misleading $0.00", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.startsWith("/appointments")) return Promise.resolve({ data: [], meta: { total: 0 } });
      if (url.startsWith("/billing/me")) return Promise.reject(new Error("network error"));
      if (url.startsWith("/notifications")) return Promise.resolve({ count: 0 });
      throw new Error(`unexpected url ${url}`);
    });

    renderWithQueryClient();

    await waitFor(() => expect(screen.getAllByText("Couldn't load").length).toBeGreaterThan(0));
    // The misleading "all paid up" / "$0.00" success copy must not appear
    // anywhere while the balance fetch is in an error state.
    expect(screen.queryByText("$0.00")).not.toBeInTheDocument();
    expect(screen.queryByText("All paid up")).not.toBeInTheDocument();
    expect(screen.queryByText("Payment due")).not.toBeInTheDocument();
  });

  it("shows the dollar amount once bills load successfully", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.startsWith("/appointments")) return Promise.resolve({ data: [], meta: { total: 0 } });
      if (url.startsWith("/billing/me")) {
        return Promise.resolve({
          data: [
            { id: "b1", amount: 40, status: "unpaid" },
            { id: "b2", amount: 60, status: "paid" },
          ],
          meta: { total: 2 },
        });
      }
      if (url.startsWith("/notifications")) return Promise.resolve({ count: 0 });
      throw new Error(`unexpected url ${url}`);
    });

    renderWithQueryClient();

    await waitFor(() => expect(screen.getByText("$40.00")).toBeInTheDocument());
    expect(screen.getByText("Payment due")).toBeInTheDocument();
    // The amber "you have an outstanding balance" banner should also appear.
    expect(screen.getByText(/outstanding balance of/i)).toBeInTheDocument();
  });

  it("does not show the outstanding-balance banner when the balance request errors", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.startsWith("/appointments")) return Promise.resolve({ data: [], meta: { total: 0 } });
      if (url.startsWith("/billing/me")) return Promise.reject(new Error("network error"));
      if (url.startsWith("/notifications")) return Promise.resolve({ count: 0 });
      throw new Error(`unexpected url ${url}`);
    });

    renderWithQueryClient();

    await waitFor(() => expect(screen.getAllByText("Couldn't load").length).toBeGreaterThan(0));
    expect(screen.queryByText(/outstanding balance of/i)).not.toBeInTheDocument();
  });

  it("shows an error state independently per card -- appointments failing doesn't blank out a working balance card", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url.startsWith("/appointments")) return Promise.reject(new Error("boom"));
      if (url.startsWith("/billing/me")) {
        return Promise.resolve({
          data: [{ id: "b1", amount: 25, status: "unpaid" }],
          meta: { total: 1 },
        });
      }
      if (url.startsWith("/notifications")) return Promise.resolve({ count: 2 });
      throw new Error(`unexpected url ${url}`);
    });

    renderWithQueryClient();

    await waitFor(() => expect(screen.getByText("$25.00")).toBeInTheDocument());
    expect(screen.getAllByText("Couldn't load").length).toBeGreaterThan(0);
  });
});
