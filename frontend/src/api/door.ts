import api from "./client";
import type { DoorAccessResult } from "./types";

export interface GuestDoorSession {
  guest: string;
  room: string;
  expires_at: string;
  message: string;
}

export const validatePin = (room_public_id: string, pin: string) =>
  api.post<GuestDoorSession>(`/door/${encodeURIComponent(room_public_id)}/session`, { pin }).then((r) => r.data);
export const getDoorSession = (room: string) =>
  api.get<GuestDoorSession>(`/door/${encodeURIComponent(room)}/session`).then((r) => r.data);
export const unlockDoor = (room: string) =>
  api.post<DoorAccessResult>(`/door/${encodeURIComponent(room)}/unlock`, {}).then((r) => r.data);
export const forgetDoorSession = (room: string) =>
  api.post(`/door/${encodeURIComponent(room)}/logout`, {});
