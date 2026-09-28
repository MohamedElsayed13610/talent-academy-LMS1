import type { Metadata, Viewport } from "next";
import { plexArabic, inter, plexMono } from "@/lib/fonts";
import { themeBootstrapScript } from "@/lib/theme-script";
import { Providers } from "@/app/providers";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Talent Academy",
  description: "منصة Talent Academy التعليمية لطلاب الدبلومة الأمريكية.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f9fc" },
    { media: "(prefers-color-scheme: dark)", color: "#081729" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ar" dir="rtl" className={`${plexArabic.variable} ${inter.variable} ${plexMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrapScript }} />
      </head>
      <body suppressHydrationWarning>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
