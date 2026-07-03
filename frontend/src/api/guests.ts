import api from "./client";
import type { Guest } from "./types";

export const getGuests = () => api.get<Guest[]>("/guests").then((r) => r.data);

export const getGuest = (id: number) =>
  api.get<Guest>(`/guests/${id}`).then((r) => r.data);

export const createGuest = (data: Omit<Guest, "id" | "created_at" | "updated_at">) =>
  api.post<Guest>("/guests", data).then((r) => r.data);

export const updateGuest = (id: number, data: Partial<Omit<Guest, "id" | "created_at" | "updated_at">>) =>
  api.patch<Guest>(`/guests/${id}`, data).then((r) => r.data);

export const deleteGuest = (id: number) =>
  api.delete(`/guests/${id}`);
