import { Navigate, Outlet } from "react-router-dom";

import { useMe } from "../hooks/useMe";

/** Layout route guard: only admins may reach Property-management pages. */
export default function RequireAdmin() {
  const { data: user } = useMe();
  if (user && user.role !== "admin") {
    return <Navigate to="/app/dashboard" replace />;
  }
  return <Outlet />;
}
