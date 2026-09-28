import { Badge, type BadgeProps } from "@/components/ui/badge";

/** One mapping for every status enum in the app, so wording is identical everywhere it appears
 * (DESIGN.md §6 StatusBadge). */
const MAP: Record<string, { label: string; tone: NonNullable<BadgeProps["tone"]> }> = {
  // subscription
  active: { label: "نشط", tone: "success" },
  pending: { label: "قيد الانتظار", tone: "warning" },
  expired: { label: "منتهي", tone: "danger" },
  suspended: { label: "موقوف", tone: "danger" },
  // student type
  academy: { label: "طالب الأكاديمية", tone: "primary" },
  external: { label: "طالب خارجي", tone: "neutral" },
  // account
  true: { label: "نشط", tone: "success" },
  false: { label: "موقوف", tone: "neutral" },
};

export function StatusBadge({ value }: { value: string | boolean }) {
  const key = String(value);
  const entry = MAP[key] || { label: key, tone: "neutral" as const };
  return <Badge tone={entry.tone}>{entry.label}</Badge>;
}
