import { NavLink, Outlet } from "react-router-dom";
import { Users, BedDouble, Link2, ClipboardList, Hotel } from "lucide-react";
import { clsx } from "clsx";

const nav = [
  { to: "guests", label: "Guests", icon: Users },
  { to: "rooms", label: "Rooms", icon: BedDouble },
  { to: "assignments", label: "Assignments", icon: Link2 },
  { to: "audit", label: "Audit Log", icon: ClipboardList },
];

export default function AdminLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside className="w-60 flex-shrink-0 bg-brand-900 flex flex-col">
        <div className="flex items-center gap-3 px-6 py-5 border-b border-brand-800">
          <Hotel className="text-brand-300" size={24} />
          <span className="text-white font-semibold text-lg tracking-tight">
            Guesthouse
          </span>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                clsx(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-brand-700 text-white"
                    : "text-brand-200 hover:bg-brand-800 hover:text-white"
                )
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-6 py-4 text-xs text-brand-400 border-t border-brand-800">
          Single-tenant · v1.0
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
