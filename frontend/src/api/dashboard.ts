import api from "./client";
import type { DashboardFloors } from "./types";

export const getFloors = () =>
  api.get<DashboardFloors>("/dashboard/floors").then((r) => r.data);
