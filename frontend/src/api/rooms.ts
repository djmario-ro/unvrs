import api from "./client";
import type { Room } from "./types";

export const getRooms = () => api.get<Room[]>("/rooms").then((r) => r.data);

export const getRoom = (id: number) =>
  api.get<Room>(`/rooms/${id}`).then((r) => r.data);

export const createRoom = (data: Omit<Room, "id" | "created_at">) =>
  api.post<Room>("/rooms", data).then((r) => r.data);

export const updateRoom = (id: number, data: Partial<Omit<Room, "id" | "created_at">>) =>
  api.patch<Room>(`/rooms/${id}`, data).then((r) => r.data);

export const deleteRoom = (id: number) => api.delete(`/rooms/${id}`);

export const getRoomQrUrl = (id: number) => `/api/v1/rooms/${id}/qr`;
