import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  NavLink,
  Navigate,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { Hotel, LogOut, Menu, X } from "lucide-react";
import { clsx } from "clsx";
import { logout } from "../api/auth";
import { useMe } from "../hooks/useMe";
import {
  hasRole,
  MANAGERS,
  RECEPTION,
  HOUSEKEEPING,
  MAINTENANCE,
} from "../lib/access";
import type { Role } from "../api/types";
import Spinner from "../components/Spinner";

const sections: { label: string; roles: Role[]; links: [string, string][] }[] =
  [
    {
      label: "Front desk",
      roles: RECEPTION,
      links: [
        ["dashboard", "Dashboard"],
        ["calendar", "Calendar"],
        ["booking", "New booking"],
        ["guests", "Guests"],
        ["bookings", "Bookings"],
      ],
    },
    {
      label: "Property",
      roles: MANAGERS,
      links: [
        ["rooms", "Rooms"],
        ["users", "Staff access"],
        ["audit", "Audit log"],
        ["whatsapp", "WhatsApp"],
      ],
    },
    {
      label: "Housekeeping",
      roles: HOUSEKEEPING,
      links: [["housekeeping", "Housekeeping"]],
    },
    {
      label: "Maintenance",
      roles: MAINTENANCE,
      links: [["maintenance", "Maintenance"]],
    },
    { label: "Owner", roles: ["owner"], links: [["properties", "Properties"]] },
  ];

export default function AppLayout() {
  const { data: user, isLoading, isError } = useMe();
  const location = useLocation(),
    nav = useNavigate(),
    qc = useQueryClient();
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => setMobileOpen(false), [location.pathname]);
  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: (result) => {
      qc.clear();
      sessionStorage.removeItem("unvrs-property");
      if (result.logout_url) window.location.assign(result.logout_url);
      else nav("/login", { replace: true });
    },
  });
  if (isLoading)
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner />
      </div>
    );
  if (isError || !user) return <Navigate to="/login" replace />;
  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <header className="lg:hidden fixed top-0 inset-x-0 z-30 h-14 bg-brand-900 flex items-center gap-3 px-4 text-white">
        <button aria-label="Open menu" onClick={() => setMobileOpen(true)}>
          <Menu />
        </button>
        <Hotel />
        {user.properties.find((p) => p.id === user.property_id)?.name}
      </header>
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/40"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        className={clsx(
          "w-60 flex-shrink-0 bg-brand-900 text-white flex flex-col z-50 fixed inset-y-0 left-0 transform transition-transform lg:static lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center gap-3 p-5 border-b border-brand-800">
          <Hotel />
          <span className="font-semibold">UNVRS</span>
          <button
            className="lg:hidden ml-auto"
            aria-label="Close menu"
            onClick={() => setMobileOpen(false)}
          >
            <X />
          </button>
        </div>
        <div className="p-3">
          <label
            htmlFor="property"
            className="block text-xs text-brand-200 mb-1"
          >
            Property
          </label>
          <select
            id="property"
            value={user.property_id}
            className="w-full bg-brand-800 rounded-lg p-2 text-sm"
            onChange={(e) => {
              sessionStorage.setItem("unvrs-property", e.target.value);
              qc.clear();
              window.location.assign("/app");
            }}
          >
            {user.properties.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <nav className="flex-1 overflow-y-auto px-3">
          {sections
            .filter((s) => hasRole(user, s.roles))
            .map((section) => (
              <div key={section.label} className="mb-3">
                <p className="text-xs uppercase text-brand-300 px-3 py-2">
                  {section.label}
                </p>
                {section.links.map(([path, label]) => (
                  <NavLink
                    key={path}
                    to={`/app/${path}`}
                    className={({ isActive }) =>
                      clsx(
                        "block px-3 py-2 rounded-lg text-sm",
                        isActive
                          ? "bg-brand-700 text-white"
                          : "text-brand-200 hover:bg-brand-800",
                      )
                    }
                  >
                    {label}
                  </NavLink>
                ))}
              </div>
            ))}
        </nav>
        <div className="p-4 border-t border-brand-800">
          <p className="font-medium">{user.username}</p>
          <p className="text-xs text-brand-200 capitalize mb-3">
            {user.roles.join(", ")}
          </p>
          <button
            className="flex items-center gap-2 text-sm"
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0 overflow-y-auto pt-14 lg:pt-0">
        <Outlet />
      </main>
    </div>
  );
}
