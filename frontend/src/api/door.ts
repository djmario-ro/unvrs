import api from "./client";
import type { DoorAccessResult } from "./types";

export const validatePin = (room_id: number, pin: string) =>
  api
    .post<DoorAccessResult>("/door/validate-pin", { room_id, pin })
    .then((r) => r.data);

export const logout = () => api.post("/door/logout");
