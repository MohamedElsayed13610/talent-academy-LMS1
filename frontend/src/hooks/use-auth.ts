"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { LoginResponse, Me } from "@/lib/types";

export function useMe() {
  return useQuery<Me>({
    queryKey: ["auth", "me"],
    queryFn: () => api.get<Me>("/auth/me"),
    retry: false,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation<LoginResponse, ApiError, { identifier: string; password: string; remember: boolean }>({
    mutationFn: (payload) => api.post<LoginResponse>("/auth/login", payload),
    onSuccess: (data) => {
      queryClient.setQueryData(["auth", "me"], data.user);
      // must_change_password is informational only (not enforced) — every account goes straight
      // to its usual destination regardless of it. Changing the password is optional, from Profile.
      router.push(data.user.role === "admin" ? "/admin" : "/dashboard");
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  const router = useRouter();

  return useMutation({
    mutationFn: () => api.post("/auth/logout"),
    onSettled: () => {
      queryClient.setQueryData(["auth", "me"], null);
      router.push("/login");
    },
  });
}
