import api from "./client";
import type { User } from "./types";

export const login = (username: string, password: string) =>
  api.post<User>("/auth/login", { username, password }).then((r) => r.data);

export const logout = () => api.post<{ logout_url: string | null }>("/auth/logout").then((r) => r.data);

export interface AuthConfig {
  provider: "local" | "keycloak";
  login_url: string | null;
}

export const getAuthConfig = () => api.get<AuthConfig>("/auth/config").then((r) => r.data);

export const getMe = () => api.get<User>("/auth/me").then((r) => r.data);
