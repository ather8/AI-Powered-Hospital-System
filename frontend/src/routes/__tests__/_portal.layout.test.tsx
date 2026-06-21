/**
 * Tests for src/routes/_portal.tsx, the shared shell around every
 * /portal/* page: top nav, sign-out, and the "finish your profile" banner
 * that's driven by a /patients/me fetch.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import React from "react";

vi.mock("@tanstack/react-router", () => import("@/test/mockRouter"));

const mockLogout = vi.fn();
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { email: "jane@example.com", role: "patient", id: "1" },
    logout: mockLogout,
  }),
}));

const mockGet = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { get: (...args: any[]) => mockGet(...args) },
  getToken: () => "fake-token",
}));

import { Route } from "@/routes/_portal";

const PortalLayout = (Route as any).options.component;

function renderLayout() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <PortalLayout />
    </QueryClientProvider>,
  );
}

describe("PortalLayout", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockLogout.mockReset();
  });

  it("renders the patient-facing nav items and the signed-in user's email", async () => {
    mockGet.mockResolvedValue({ id: "patient-1" });
    renderLayout();

    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Appointments")).toBeInTheDocument();
    expect(screen.getByText("Bills & Payments")).toBeInTheDocument();
    expect(screen.getByText("My Records")).toBeInTheDocument();
    expect(screen.getByText("Notifications")).toBeInTheDocument();
    expect(screen.getByText("jane@example.com")).toBeInTheDocument();
  });

  it("calls logout when 'Sign out' is clicked", async () => {
    mockGet.mockResolvedValue({ id: "patient-1" });
    renderLayout();

    await userEvent.click(screen.getByRole("button", { name: /sign out/i }));
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  it("shows the 'finish setting up your account' banner when the patient has no profile yet", async () => {
    // /patients/me resolving falsy (no linked Patient record) is how an
    // unfinished signup looks to this page.
    mockGet.mockResolvedValue(null);
    renderLayout();

    await waitFor(() =>
      expect(screen.getByText(/finish setting up your account/i)).toBeInTheDocument(),
    );
    expect(screen.getByText("Create my profile")).toBeInTheDocument();
  });

  it("does not show the profile banner once a profile exists", async () => {
    mockGet.mockResolvedValue({ id: "patient-1" });
    renderLayout();

    // Wait for the query to settle, then assert the banner never appeared.
    await waitFor(() => expect(mockGet).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.queryByText(/finish setting up your account/i)).not.toBeInTheDocument(),
    );
  });

  it("does not show the profile banner while the profile check is still in flight", () => {
    mockGet.mockReturnValue(new Promise(() => {})); // never resolves during this test
    renderLayout();

    expect(screen.queryByText(/finish setting up your account/i)).not.toBeInTheDocument();
  });
});
