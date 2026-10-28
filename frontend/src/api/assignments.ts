import api from "./client";
import type { Assignment } from "./types";

// Ask for the server's maximum; the calendar and dashboard derive availability
// from this list, so a silently truncated page shows wrong availability.
export const getAssignments = () =>
  api
    .get<Assignment[]>("/assignments", { params: { limit: 500 } })
    .then((r) => r.data);

export const createAssignment = (data: {
  guest_id: number;
  room_id: number;
  check_in?: string | null;
  check_out?: string | null;
}) => api.post<Assignment>("/assignments", data).then((r) => r.data);

export const updateAssignment = (
  id: number,
  data: { room_id?: number; check_in?: string | null; check_out?: string | null }
) => api.patch<Assignment>(`/assignments/${id}`, data).then((r) => r.data);

export const deleteAssignment = (id: number) => api.delete(`/assignments/${id}`);

export const regeneratePin = (id: number) =>
  api.post<Assignment>(`/assignments/${id}/regenerate-pin`).then((r) => r.data);
