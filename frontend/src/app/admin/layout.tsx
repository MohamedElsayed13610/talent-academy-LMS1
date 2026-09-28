import { AdminShell } from "@/components/shells/admin-shell";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <AdminShell>{children}</AdminShell>;
}
