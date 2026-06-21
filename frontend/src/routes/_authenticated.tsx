import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { AppSidebar } from "@/components/app-sidebar";
import { SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { getToken } from "@/lib/api";

export const Route = createFileRoute("/_authenticated")({
  beforeLoad: ({ location }) => {
    // SSR-safe: getToken returns null on server, which is fine — client navigation
    // re-runs beforeLoad with localStorage available.
    if (typeof window !== "undefined" && !getToken()) {
      throw redirect({ to: "/login", search: { redirect: location.href } });
    }
  },
  component: AuthLayout,
});

function AuthLayout() {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-background">
        <AppSidebar />
        <div className="flex flex-1 flex-col">
          <header className="sticky top-0 z-10 flex h-12 items-center gap-2 border-b bg-background/80 px-3 backdrop-blur">
            <SidebarTrigger />
            <div className="text-xs uppercase tracking-wider text-muted-foreground">Aetheris Workspace</div>
          </header>
          <main className="flex-1 p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
