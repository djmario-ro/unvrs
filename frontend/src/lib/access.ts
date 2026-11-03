import type { Role, User } from "../api/types";
export const MANAGERS: Role[] = ["owner", "administrator"];
export const RECEPTION: Role[] = [...MANAGERS, "frontdesk"];
export const HOUSEKEEPING: Role[] = [...MANAGERS, "housekeeping"];
export const MAINTENANCE: Role[] = [...MANAGERS, "maintenance"];
export const hasRole = (user: User | undefined, roles: Role[]) =>
  !!user?.roles.some((r) => roles.includes(r));
export const homeFor = (user: User) =>
  hasRole(user, RECEPTION)
    ? "/app/dashboard"
    : hasRole(user, HOUSEKEEPING)
      ? "/app/housekeeping"
      : "/app/maintenance";
