/**
 * Route files in src/routes/ define their component via
 * createFileRoute(path)({ component: Foo }) and only export `Route` (not
 * the component itself). Rather than changing production code just to make
 * components individually exportable, tests mock @tanstack/react-router so
 * `Route.options.component` resolves to the real component function, which
 * can then be rendered directly with React Testing Library.
 *
 * Usage in a test file:
 *   vi.mock("@tanstack/react-router", () => import("@/test/mockRouter"));
 *   import { Route } from "@/routes/_portal.overview";
 *   const Component = Route.options.component;
 */
import { vi } from "vitest";
import React from "react";

export function createFileRoute(_path: string) {
  return (options: any) => ({ options, path: _path });
}

export const Link = ({ to, children, ...rest }: any) =>
  React.createElement("a", { href: to, ...rest }, children);

export const Outlet = () => null;

export function redirect(opts: any) {
  // Mirrors the real TanStack Router contract: redirect() throws a
  // special object rather than returning one.
  throw opts;
}

export const useNavigate = () => vi.fn();
export const useRouter = () => ({ navigate: vi.fn() });
export const useParams = () => ({});
export const useSearch = () => ({});
