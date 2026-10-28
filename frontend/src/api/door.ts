import api from "./client";
import type { DoorAccessResult } from "./types";

export const validatePin = (room_public_id: string, pin: string) =>
  api
    .post<DoorAccessResult>("/door/validate-pin", { room_public_id, pin })
    .then((r) => r.data);
