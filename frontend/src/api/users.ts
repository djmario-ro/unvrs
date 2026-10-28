import api from "./client";
import type { Role, User } from "./types";

export const getUsers = () => api.get<User[]>("/users").then((r) => r.data);

export const createUser = (data: {
  username: string;
  password: string;
  role: Role;
}) => api.post<User>("/users", data).then((r) => r.data);

export const updateUser = (
  id: number,
  data: { password?: string; role?: Role }
) => api.patch<User>(`/users/${id}`, data).then((r) => r.data);

export const deleteUser = (id: number) => api.delete(`/users/${id}`);
