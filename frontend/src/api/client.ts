import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error.response?.status;
    const url: string = error.config?.url ?? "";
    // Session expired mid-use: bounce to login (but not for the auth probes
    // themselves, which the auth flow handles explicitly).
    if (
      status === 401 &&
      !url.startsWith("/auth/") &&
      window.location.pathname.startsWith("/app")
    ) {
      window.location.href = "/login";
    }
    const detail = error.response?.data?.detail;
    // FastAPI validation errors (422) carry a list of {loc, msg}; flatten it
    // into something a toast can show instead of "[object Object]".
    const message = Array.isArray(detail)
      ? detail
          .map((d: { loc?: unknown[]; msg?: string }) => {
            const field = Array.isArray(d.loc) ? d.loc.filter((l) => l !== "body").join(".") : "";
            return field ? `${field}: ${d.msg}` : d.msg;
          })
          .join("; ")
      : detail ?? error.message ?? "An error occurred";
    return Promise.reject(new Error(message));
  }
);

export default api;
