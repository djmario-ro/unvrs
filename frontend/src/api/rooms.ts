import api from "./client";
import type { Room, RoomImage, RoomInput } from "./types";

export const getRooms = () => api.get<Room[]>("/rooms").then((r) => r.data);

export const getRoom = (id: number) =>
  api.get<Room>(`/rooms/${id}`).then((r) => r.data);

export const createRoom = (data: RoomInput) =>
  api.post<Room>("/rooms", data).then((r) => r.data);

export const updateRoom = (id: number, data: Partial<RoomInput>) =>
  api.patch<Room>(`/rooms/${id}`, data).then((r) => r.data);

export const deleteRoom = (id: number) => api.delete(`/rooms/${id}`);

export const markRoomCleaned = (id: number) => api.post(`/rooms/${id}/cleaned`);

export const getRoomQrUrl = (id: number) => `/api/v1/rooms/${id}/qr`;

export const getRoomImageUrl = (roomId: number, imageId: number, width?: number) =>
  `/api/v1/rooms/${roomId}/images/${imageId}${width ? `?w=${width}` : ""}`;

export const uploadRoomImage = (roomId: number, file: File) => {
  const data = new FormData();
  data.append("file", file);
  return api
    .post<RoomImage>(`/rooms/${roomId}/images`, data, {
      // Let the browser set multipart/form-data with the correct boundary.
      headers: { "Content-Type": undefined } as never,
    })
    .then((r) => r.data);
};

export const deleteRoomImage = (roomId: number, imageId: number) =>
  api.delete(`/rooms/${roomId}/images/${imageId}`);

export const setCoverImage = (roomId: number, imageId: number) =>
  api.post<RoomImage>(`/rooms/${roomId}/images/${imageId}/cover`).then((r) => r.data);
