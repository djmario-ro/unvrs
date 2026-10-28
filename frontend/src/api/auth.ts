import api from "./client";
import type { User } from "./types";

export const login = (username: string, password: string) =>
  api.post<User>("/auth/login", { username, password }).then((r) => r.data);

export const logout = () => api.post("/auth/logout");

export const getMe = () => api.get<User>("/auth/me").then((r) => r.data);
