"use client";

import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster, toast } from "sonner";
import { useState } from "react";
import { BrandingEffect } from "@/components/branding-effect";
import { ApiError } from "@/lib/api";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1 },
        },
        // Global safety net: every mutation error shows a toast here, regardless of whether the
        // calling page's own try/catch (if any) also handles it. This is what actually stops a
        // page-level bug — a `mutateAsync` call with no try/catch around it — from turning a
        // routine backend error into an uncaught promise rejection and a Next.js error overlay.
        // Callers can still opt out per-call with `meta: { silent: true }` when they render the
        // error inline instead (e.g. a create-student form showing its own message).
        mutationCache: new MutationCache({
          onError: (error, _variables, _context, mutation) => {
            if (mutation.options.meta?.silent) return;
            toast.error(error instanceof ApiError ? error.message : "حدث خطأ غير متوقع");
          },
        }),
      }),
  );

  return (
    <QueryClientProvider client={client}>
      <BrandingEffect />
      {children}
      <Toaster position="top-center" dir="rtl" richColors closeButton />
    </QueryClientProvider>
  );
}
