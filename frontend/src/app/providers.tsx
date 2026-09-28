"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { useState } from "react";
import { BrandingEffect } from "@/components/branding-effect";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1 },
        },
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
