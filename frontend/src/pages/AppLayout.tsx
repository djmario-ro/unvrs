import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  NavLink,
  Navigate,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Hotel,
  LayoutDashboard,
  BedDouble,
  MessageCircle,
  ClipboardList,
  ShieldCheck,
  CalendarPlus,
  CalendarRange,
  Users,
  CalendarCheck,
  Building2,
  ConciergeBell,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { clsx } from "clsx";

import { logout } from "../api/auth";
import { useMe } from "../hooks/useMe";
import Spinner from "../components/Spinner";

const FRONTDESK_NAV = [
  { to: "/app/calendar", label: "Calendar", icon: CalendarRange },
  { to: "/app/booking", label: "New Booking", icon: CalendarPlus },
  { to: "/app/guests", label: "Guests", icon: Users },
  { to: "/app/bookings", label: "Bookings", icon: CalendarCheck },
];

const PROPERTY_NAV = [
  { to: "/app/rooms", label: "Rooms", icon: BedDouble },
  { to: "/app/whatsapp", label: "WhatsApp", icon: MessageCircle },
  { to: "/app/audit", label: "Audit Log", icon: ClipboardList },
  { to: "/app/users", label: "Users", icon: ShieldCheck },
];

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  clsx(
    "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
    isActive
      ? "bg-brand-700 text-white"
      : "text-brand-200 hover:bg-brand-800 hover:text-white"
  );

export default function AppLayout() {
  const { data: user, isLoading, isError } = useMe();
  const location = useLocation();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => setMobileOpen(false), [location.pathname]);

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      qc.clear();
      nav("/login", { replace: true });
    },
  });

  if (isLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <Spinner size={32} />
      </div>
    );
  }
  if (isError || !user) return <Navigate to="/login" replace />;

  const isAdmin = user.role === "admin";
  const onProperty = PROPERTY_NAV.some((n) => n.to === location.pathname);
  const section: "property" | "frontdesk" =
    isAdmin && onProperty ? "property" : "frontdesk";
  const items = section === "property" ? PROPERTY_NAV : FRONTDESK_NAV;

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Mobile top bar */}
      <header className="lg:hidden fixed top-0 inset-x-0 z-30 h-14 bg-brand-900 flex items-center gap-3 px-4">
        <button
          onClick={() => setMobileOpen(true)}
          aria-label="Open menu"
          className="text-white p-1 -ml-1"
        >
          <Menu size={22} />
        </button>
        <Hotel className="text-brand-300" size={20} />
        <span className="text-white font-semibold tracking-tight">Retreat 480</span>
      </header>

      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/40"
          onClick={() => setMobileOpen(false)}
          aria-hidden
        />
      )}

      <aside
        className={clsx(
          "w-60 flex-shrink-0 bg-brand-900 flex flex-col z-50",
          "fixed inset-y-0 left-0 transform transition-transform duration-200",
          "lg:static lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex items-center gap-3 px-6 py-5 border-b border-brand-800">
          <Hotel className="text-brand-300" size={24} />
          <span className="text-white font-semibold text-lg tracking-tight">
            Retreat 480
          </span>
          <button
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu"
            className="lg:hidden ml-auto text-brand-300 hover:text-white p-1"
          >
            <X size={20} />
          </button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <NavLink to="/app/dashboard" className={navLinkClass}>
            <LayoutDashboard size={18} />
            Dashboard
          </NavLink>

          {isAdmin && (
            <div className="grid grid-cols-2 gap-1 p-1 my-3 rounded-lg bg-brand-800/60">
              <button
                onClick={() => nav("/app/booking")}
                className={clsx(
                  "flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs font-medium transition-colors",
                  section === "frontdesk"
                    ? "bg-brand-600 text-white"
                    : "text-brand-200 hover:text-white"
                )}
              >
                <ConciergeBell size={14} /> Front Desk
              </button>
              <button
                onClick={() => nav("/app/rooms")}
                className={clsx(
                  "flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs font-medium transition-colors",
                  section === "property"
                    ? "bg-brand-600 text-white"
                    : "text-brand-200 hover:text-white"
                )}
              >
                <Building2 size={14} /> Property
              </button>
            </div>
          )}

          <p className="px-3 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-brand-400">
            {section === "property" ? "Property Management" : "Front Desk"}
          </p>
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={navLinkClass}>
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-brand-800 px-3 py-3">
          <div className="flex items-center gap-2 px-3 py-2 mb-1">
            <div className="w-8 h-8 rounded-full bg-brand-700 flex items-center justify-center text-sm font-semibold text-white uppercase">
              {user.username.slice(0, 2)}
            </div>
            <div className="min-w-0">
              <p className="text-sm text-white font-medium truncate">
                {user.username}
              </p>
              <p className="text-[11px] text-brand-300 capitalize">{user.role}</p>
            </div>
          </div>
          <button
            onClick={() => logoutMutation.mutate()}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-brand-200 hover:bg-brand-800 hover:text-white transition-colors"
          >
            <LogOut size={18} />
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto pt-14 lg:pt-0">
        <Outlet />
      </main>
    </div>
  );
}
