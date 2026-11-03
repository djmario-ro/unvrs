import { Navigate, Outlet } from "react-router-dom";
import { useMe } from "../hooks/useMe";
import { hasRole, homeFor } from "../lib/access";
import type { Role } from "../api/types";
export default function RequireRoles({ roles }: { roles: Role[] }) {
  const { data: user } = useMe();
  return user && hasRole(user, roles) ? (
    <Outlet />
  ) : (
    <Navigate to={user ? homeFor(user) : "/login"} replace />
  );
}
