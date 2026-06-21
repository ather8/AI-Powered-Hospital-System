import { Link, useRouterState } from "@tanstack/react-router";
import {
  Activity,
  Brain,
  CalendarClock,
  ClipboardList,
  CreditCard,
  FileSearch,
  FileText,
  Heart,
  LayoutDashboard,
  MessageSquare,
  NotebookPen,
  ScanText,
  Search,
  ShieldCheck,
  Stethoscope,
  UserRound,
  Users,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth";
import { ROUTE_ROLES } from "@/lib/route-guard";
import { Button } from "@/components/ui/button";
import { useUnreadNotificationCount } from "@/hooks/use-notifications";

type Item = { title: string; url: string; icon: React.ComponentType<{ className?: string }> };

const sections: { label: string; items: Item[] }[] = [
  {
    label: "Overview",
    items: [
      { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
      { title: "Search", url: "/search", icon: Search },
      { title: "Notifications", url: "/notifications", icon: Activity },
    ],
  },
  {
    label: "Clinical",
    items: [
      { title: "Patients", url: "/patients", icon: Users },
      { title: "Doctors", url: "/doctors", icon: Stethoscope },
      { title: "Appointments", url: "/appointments", icon: CalendarClock },
      { title: "EMR", url: "/emr", icon: ClipboardList },
      { title: "Billing", url: "/billing", icon: CreditCard },
    ],
  },
  {
    label: "AI Tools",
    items: [
      { title: "Clinical Search", url: "/ai/clinical-search", icon: Brain },
      { title: "Report Summary", url: "/ai/summary", icon: FileText },
      { title: "AI Notes", url: "/ai/notes", icon: NotebookPen },
      { title: "Triage Chatbot", url: "/chatbot", icon: MessageSquare },
      { title: "OCR", url: "/ocr", icon: ScanText },
    ],
  },
  {
    label: "Admin",
    items: [
      { title: "Analytics", url: "/analytics", icon: FileSearch },
      { title: "Audit Logs", url: "/audit-logs", icon: ShieldCheck },
    ],
  },
];

export function AppSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { user, logout, hasRole } = useAuth();
  // Lets people see a new notification arrived without opening the page —
  // polls a lightweight count endpoint rather than the full list.
  const { data: unread } = useUnreadNotificationCount();
  const unreadCount = unread?.count ?? 0;

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="border-b">
        <Link to="/dashboard" className="flex items-center gap-2 px-2 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Heart className="h-4 w-4" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold">Aetheris Health</span>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">AI Hospital Platform</span>
          </div>
        </Link>
      </SidebarHeader>
      <SidebarContent>
        {sections.map((sec) => {
          const items = sec.items.filter((i) => {
            const roles = ROUTE_ROLES[i.url];
            return !roles || hasRole(roles);
          });
          if (!items.length) return null;
          return (
            <SidebarGroup key={sec.label}>
              <SidebarGroupLabel>{sec.label}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {items.map((item) => (
                    <SidebarMenuItem key={item.url}>
                      <SidebarMenuButton asChild isActive={pathname === item.url || pathname.startsWith(item.url + "/")}>
                        <Link to={item.url} className="flex items-center gap-2">
                          <item.icon className="h-4 w-4" />
                          <span className="flex-1">{item.title}</span>
                          {item.url === "/notifications" && unreadCount > 0 && (
                            <Badge variant="default" className="h-5 min-w-5 justify-center px-1.5 text-[10px]">
                              {unreadCount > 99 ? "99+" : unreadCount}
                            </Badge>
                          )}
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          );
        })}
      </SidebarContent>
      <SidebarFooter className="border-t">
        <div className="flex items-center gap-2 px-2 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
            <UserRound className="h-4 w-4" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="truncate text-sm font-medium">{user?.email ?? "Signed in"}</div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{user?.role}</div>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={logout} className="mx-2 mb-2 justify-start">
          Sign out
        </Button>
      </SidebarFooter>
    </Sidebar>
  );
}
