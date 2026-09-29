# Future public landing page (Scope F)

Not implemented yet, and nothing here adds placeholder sections or fake content for it — this
documents where it goes and how it should be built when that work is actually requested.

## Routing

- **`/` is reserved for the future public academy landing page.** It currently renders a minimal,
  real (not placeholder) branded screen — logo, tagline, a button to `/login` — in
  `frontend/src/app/page.tsx`. That file is exactly where the landing page replaces it; no new
  route needs to be created.
- **`/login` is untouched and stays exactly where it is** (`frontend/src/app/login/page.tsx`) —
  the landing page's "login" / "student portal" call-to-action should link there, the same way
  `/` already does today.
- **Every authenticated route continues to work unmodified**: the `(student)` route group
  (`/dashboard`, `/courses`, `/exams`, `/live`, `/points`, `/profile`, `/calendar`, `/lessons`,
  `/notifications`) and `/admin/*` are unrelated to `/` and need no changes for a landing page to
  ship.

## Data the landing page should use

`GET /api/v1/public/branding` (`backend/app/api/v1/public.py`) is already built for exactly this:
unauthenticated, and deliberately returns only what's safe to show publicly —

```json
{
  "display_name": "...",
  "logo_url": "...",
  "primary_color": "...",
  "accent_color": "...",
  "whatsapp_url": "..."
}
```

It never returns anything from the rest of `AcademySettings` (point values, attendance/exam
thresholds, admin accounts, audit log, backup destination) — those stay behind `GET /admin/settings`
(admin-authenticated). The landing page should call `/public/branding` for the academy name, logo,
and brand colors, the same hook pattern already used elsewhere (`frontend/src/hooks/use-branding.ts`),
and never needs a new backend endpoint for that.

If the landing page later wants richer public content (course catalog previews, published
announcements, etc.), that's new scope with its own review of what's safe to expose publicly — it
should not be assumed to come from the same branding endpoint.

## Why `/` was left alone here

Scope F's instruction is explicit: only prepare the routing, don't design or build the landing
page itself, and leave `/`'s current behavior unchanged if replacing it now risks breaking
anything. The existing `/` already satisfies everything Scope F asks of it today (a working entry
point that doesn't collide with `/login` or any authenticated route), so there was nothing to
change — just this note for whoever builds the real landing page next.
