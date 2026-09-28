// Exam scheduling is authored in Cairo local time and stored/sent as UTC (backend boundary rule
// for Phase 5 — ARCHITECTURE.md A1: "everything is stored in UTC; Cairo time is only for
// display"). Uses Intl's built-in IANA tz database instead of a hardcoded +02:00 offset, so this
// stays correct even if Egypt's DST policy changes again.
const CAIRO_TZ = "Africa/Cairo";

function cairoOffsetMinutes(date: Date): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: CAIRO_TZ, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).formatToParts(date);
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0);
  const asIfUtc = Date.UTC(get("year"), get("month") - 1, get("day"), get("hour") % 24, get("minute"), get("second"));
  return (asIfUtc - date.getTime()) / 60000;
}

/** UTC ISO string -> "YYYY-MM-DDTHH:mm" for a <input type="datetime-local"> showing Cairo time. */
export function toCairoInputValue(iso?: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: CAIRO_TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(date);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "00";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}

/** "YYYY-MM-DDTHH:mm" (interpreted as Cairo local time) -> UTC ISO string for the API. */
export function fromCairoInputValue(value: string): string {
  const [datePart = "", timePart = "00:00"] = value.split("T");
  const [y = 1970, m = 1, d = 1] = datePart.split("-").map(Number);
  const [hh = 0, mm = 0] = timePart.split(":").map(Number);
  const guessUtcMs = Date.UTC(y, m - 1, d, hh, mm);
  const offsetMinutes = cairoOffsetMinutes(new Date(guessUtcMs));
  return new Date(guessUtcMs - offsetMinutes * 60000).toISOString();
}

/** For read-only display, e.g. the exam list's starts_at/ends_at columns. */
export function formatCairo(iso?: string | null): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("ar-EG", { timeZone: CAIRO_TZ, dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}
