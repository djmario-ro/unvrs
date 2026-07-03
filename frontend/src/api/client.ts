import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    const message =
      error.response?.data?.detail ?? error.message ?? "An error occurred";
    return Promise.reject(new Error(message));
  }
);

export default api;
