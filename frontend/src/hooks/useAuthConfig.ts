import { useQuery } from "@tanstack/react-query";
import { getAuthConfig } from "../api/auth";

export const useAuthConfig = () => useQuery({
  queryKey: ["auth-config"],
  queryFn: getAuthConfig,
  staleTime: 60_000,
});
