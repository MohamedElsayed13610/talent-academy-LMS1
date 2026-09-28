import { StudentShell } from "@/components/shells/student-shell";

export default function StudentLayout({ children }: { children: React.ReactNode }) {
  return <StudentShell>{children}</StudentShell>;
}
