import api from "./client";
import type { Assignment } from "./types";

export const getAssignments = () =>
  api.get<Assignment[]>("/assignments").then((r) => r.data);

export const createAssignment = (data: {
  guest_id: number;
  room_id: number;
  check_in?: string | null;
  check_out?: string | null;
}) => api.post<Assignment>("/assignments", data).then((r) => r.data);

export const deleteAssignment = (id: number) => api.delete(`/assignments/${id}`);

export const regeneratePin = (id: number) =>
  api.post<Assignment>(`/assignments/${id}/regenerate-pin`).then((r) => r.data);
