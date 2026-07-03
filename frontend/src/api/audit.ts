import api from "./client";
import type { AuditEntry } from "./types";

export const getAuditLog = () =>
  api.get<AuditEntry[]>("/audit").then((r) => r.data);
