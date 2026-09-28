# Talent Academy LMS — Design System (Phase 0)

Status: **Draft for approval.** Section 13 of the spec asks for a completely new interface: the prototype's
features, workflow and Arabic wording stay, its visual design does not.
In Phase 1 this becomes a live `/design` preview page, and **the rest of the UI waits for your approval of it**.

Contents: [Direction](#1-direction) · [Color](#2-color) · [Typography](#3-typography) ·
[Space, radius, shadow, motion](#4-space-radius-elevation-motion) · [RTL & numbers](#5-rtl-and-numbers) ·
[Components](#6-component-inventory) · [Layout shells](#7-layout-shells) · [Key screens](#8-key-screens) ·
[States](#9-states-every-page-must-have) · [Accessibility](#10-accessibility) · [Assets](#11-assets-and-performance)

---

## 1. Direction

The feel: **a calm, premium test-prep platform** — the kind of product a student trusts with a real exam. Not
a generic admin template, and not a playful "edtech" toy.

Four rules that decide the look:

1. **Deep royal blue is the brand; white space is the interface.** Colour appears on a few anchors (primary
   buttons, active nav, progress, the dashboard hero). Everything else is neutral, so the blue always means
   "this matters".
2. **Gold is earned.** The warm gold accent is reserved for points, ranks, streaks and achievements. Never a
   default button colour.
3. **Content is a card on a soft field.** One elevation step between the page background and the cards, one
   more for dialogs and drawers. No heavy borders, no gradients on content.
4. **Comfortable, not cramped.** 16 px body text, 44 px minimum tap targets, generous line height for Arabic.

The whole of section 2 is implemented as CSS variables set on `:root` (and `[data-theme="dark"]`). Brand
colours come from `academy_settings` and are injected server-side as inline `:root` overrides, so no component
ever hardcodes a brand colour.

---

## 2. Color

Primary hue is taken from the logo's ring (`#0866ff`) and its deep shield navy (`#14375f`), then built into a
proper ramp. `--primary` is the accessible action colour (4.6:1 on white); the raw logo blue is kept as
`--brand-bright` for the logo lockup and focus rings only.

### 2.1 Ramps

| Token | Light | Dark | Use |
|---|---|---|---|
| `--brand-50` | `#eff5ff` | — | tinted surfaces, selected rows |
| `--brand-100` | `#dbe8fe` | — | badges, progress track |
| `--brand-200` | `#bcd5fd` | — | borders on brand surfaces |
| `--brand-300` | `#8ebafb` | — | dark-mode text on brand |
| `--brand-400` | `#5b95f8` | — | dark-mode primary hover |
| `--brand-500` | `#2f74f0` | — | dark-mode primary |
| `--brand-600` | `#1a5ad9` | — | **`--primary` (light)** |
| `--brand-700` | `#1748ae` | — | primary hover/pressed |
| `--brand-800` | `#14375f` | — | logo navy, headings on brand |
| `--brand-900` | `#0d2542` | — | dark surfaces |
| `--brand-950` | `#081729` | — | dark page background |
| `--gold-400` | `#f2c14e` | | points/rank accent (dark mode) |
| `--gold-500` | `#d99f1f` | | points/rank accent (light) |
| `--gold-600` | `#a97512` | | gold text on light, icons |

Neutrals are a slightly blue-cast grey (`--n-0 #ffffff`, `50 #f7f9fc`, `100 #eef2f7`, `200 #e2e8f0`,
`300 #cbd5e1`, `400 #94a3b8`, `500 #64748b`, `600 #475569`, `700 #334155`, `800 #1e293b`, `900 #0f172a`).

### 2.2 Semantic tokens

| Token | Light | Dark |
|---|---|---|
| `--bg` | `--n-50` | `--brand-950` |
| `--surface` | `#ffffff` | `#10233c` |
| `--surface-2` (nested, table head) | `--n-50` | `#16304f` |
| `--surface-raised` (dialog, drawer, popover) | `#ffffff` | `#193a5f` |
| `--border` | `--n-200` | `#24405f` |
| `--border-strong` | `--n-300` | `#31527a` |
| `--text` | `--n-900` | `#eef4fb` |
| `--text-muted` | `--n-500` | `#9db1c9` |
| `--text-subtle` | `--n-400` | `#7d94ad` |
| `--primary` / `--primary-hover` / `--primary-fg` | `--brand-600` / `--brand-700` / `#fff` | `--brand-500` / `--brand-400` / `#06182c` |
| `--primary-soft` / `--primary-soft-fg` | `--brand-50` / `--brand-700` | `rgba(47,116,240,.16)` / `--brand-300` |
| `--accent` (gold) / `--accent-soft` | `--gold-500` / `#fdf6e3` | `--gold-400` / `rgba(242,193,78,.16)` |
| `--ring` | `--brand-bright` (`#0866ff`) | `--brand-400` |

### 2.3 Status colours

Each has `-fg` (text/icon) and `-soft` (background) so badges keep ≥4.5:1 contrast in both themes.

| Meaning | Where it appears | Light fg / soft |
|---|---|---|
| success / حاضر / ناجح / نشط / منشور | attendance, results, subscription | `#137a4b` / `#e7f6ee` |
| warning / متأخر / قيد الانتظار / timer amber | attendance, subscription, exam timer | `#a2660a` / `#fdf3e0` |
| danger / غائب / راسب / منتهي / موقوف / locked / timer red | attendance, results, lock states | `#c0392f` / `#fdecea` |
| info / بعذر / قادم / مسودة | attendance, exam state | `#1a5ad9` / `#eff5ff` |
| neutral / غير محدد / ended | attendance, past items | `--n-600` / `--n-100` |

`--live`: `#e11d48` with a slow-pulsing dot, used only for a session that is happening now.

**Course accents** (A14) are 7 tokens — blue, navy, sky, teal, gold, violet, rose — each defined as a
`{-fg, -soft, -bar}` triple, checked in both themes. A course card uses the accent only for its subject chip,
progress bar and left edge; the card body stays neutral.

### 2.4 Dark mode
Light is the default. Dark mode follows the OS and can be overridden by a toggle in the profile menu, stored in
`localStorage` and mirrored to a cookie so the server renders `data-theme` on the first paint (no flash).
Dark surfaces are deep navy, not pure black, so the brand still reads. Exam question images always sit on a
white plate, in both themes, because the scans have white backgrounds.

---

## 3. Typography

| | Font | Loading |
|---|---|---|
| Arabic + UI | **IBM Plex Sans Arabic** (400/500/600/700) | `next/font/google`, self-hosted, `display: swap`, subset `arabic + latin` |
| Latin / numbers in Arabic text | **Inter** (400/500/600/700) | same, `latin` subset |
| Exam content, code, student codes | **IBM Plex Mono** (500/600) | `latin` subset |

`--font-sans: var(--font-plex-arabic), var(--font-inter), system-ui, sans-serif` — the Arabic face first, so
mixed Arabic/Latin lines stay consistent; Inter picks up characters Plex Arabic doesn't cover.

Scale (`clamp()` where noted; base 16 px):

| Token | Size / line-height | Weight | Use |
|---|---|---|---|
| `display` | `clamp(28px, 4vw, 40px)` / 1.25 | 700 | dashboard greeting, result score |
| `h1` | `clamp(24px, 3vw, 30px)` / 1.3 | 700 | page titles |
| `h2` | 22px / 1.35 | 600 | section titles |
| `h3` | 18px / 1.4 | 600 | card titles |
| `body-lg` | 17px / 1.75 | 400 | exam text, lesson descriptions |
| `body` | **16px** / 1.7 | 400 | default |
| `body-sm` | 14px / 1.6 | 400 | table cells, secondary text |
| `label` | 14px / 1.4 | 500 | form labels, nav |
| `caption` | 13px / 1.5 | 400 | helper text, timestamps |
| `overline` | 12px / 1.4, `letter-spacing: .08em`, uppercase | 600 | Latin section kickers ("EXAM SECURITY") — Latin only, never Arabic |
| `metric` | `clamp(28px, 3vw, 36px)` / 1.1, `tabular-nums` | 700 | stat tiles, timer |

Arabic gets `line-height: 1.7–1.8` and never `letter-spacing` or `text-transform` (both break Arabic shaping).

---

## 4. Space, radius, elevation, motion

- **Space scale** (4 px base): 1=4, 2=8, 3=12, 4=16, 5=20, 6=24, 8=32, 10=40, 12=48, 16=64.
  Card padding 24 (20 on mobile), grid gap 24 (16 on mobile), form field gap 20, section gap 32–40.
- **Radius:** `sm 8` (chips, inputs inside groups), `md 12` (buttons, inputs), `lg 16` (cards), `xl 24`
  (hero, dialogs), `full` (avatars, pills).
- **Elevation:** `sh-1 0 1px 2px rgb(15 23 42/.06), 0 1px 3px rgb(15 23 42/.04)` (cards) ·
  `sh-2 0 4px 12px rgb(15 23 42/.08)` (hover, popovers) ·
  `sh-3 0 16px 40px rgb(15 23 42/.16)` (dialogs, drawers, mobile nav).
  In dark mode shadows shrink and a `--border` outline carries the separation instead.
- **Motion:** `--t-fast 120ms`, `--t 180ms`, `--t-slow 260ms`, easing `cubic-bezier(.2,.8,.25,1)`.
  Hover/press 120 ms; drawers and dialogs 180–260 ms; progress rings animate once on mount (600 ms).
  Everything inside `@media (prefers-reduced-motion: reduce)` drops to `1ms` and the live-dot pulse stops.

---

## 5. RTL and numbers

- `<html lang="ar" dir="rtl">`. Layout uses **logical properties only** (`margin-inline-start`,
  `padding-inline`, `inset-inline-start`, `border-start-start-radius`). Tailwind's `ps/pe/ms/me/start/end`
  utilities, never `pl/pr/left/right`.
- **Directional icons flip** (chevrons, arrows, back) via a `.rtl-flip` class, `scaleX(-1)`. Icons that are not
  directional (clock, play, check, trophy) never flip.
- **LTR islands** in the RTL page, each `dir="ltr"` with `text-align: start`: exam question text and images,
  choice labels A/B/C/D, student codes, emails, URLs, phone numbers, the answer-key textarea, and the timer.
- **Numbers** use Western digits (0-9) everywhere, including Arabic text — the academy's own sheets, student
  codes and scores use them. Formatting uses `Intl.NumberFormat("ar-EG-u-nu-latn")`.
- **Dates/times** are formatted in `Africa/Cairo` with `Intl.DateTimeFormat("ar-EG-u-nu-latn", {timeZone})`.
  Relative times ("منذ ٣ دقائق") use `Intl.RelativeTimeFormat`, with the absolute time in the tooltip.

---

## 6. Component inventory

Base: **shadcn/ui (Radix)**, fully restyled to the tokens above — we keep its accessibility behaviour
(focus traps, roving tabindex, `aria-*`) and replace all of its visuals.

**Primitives** — Button (`primary` / `secondary` / `ghost` / `danger` / `gold`; sizes sm 36 / md 44 / lg 52;
`loading` state with a spinner that keeps the label width) · IconButton (44 px hit area) · Input, Textarea,
Select, Combobox (student/course search), DatePicker + TimePicker (Cairo-labelled), Checkbox, Radio, Switch,
Slider · Field wrapper (label + hint + error + `aria-describedby`) · Badge (status + course accent) · Chip
(removable, for enrollments/groups) · Avatar (initials on a hashed brand tint) · Tooltip · Popover ·
DropdownMenu · Dialog · **Drawer** (side sheet — the admin's default editing surface) · Sheet (mobile nav) ·
Tabs · Accordion · Progress (bar + **ring**) · Separator · Skeleton · Toast (`sonner`, top-center, RTL) ·
Pagination · ScrollArea · Command palette (admin `Ctrl/⌘+K`).

**Composites**
- `PageHeader` — title, description, breadcrumb, actions; sticky-on-scroll compact variant.
- `StatTile` — icon, label, metric, delta; used in every overview strip.
- `DataTable` — server-driven sorting/filtering/pagination, sticky header, row selection with a floating
  bulk-action bar, per-row action menu, and a **card list fallback under 768 px** (tables never scroll
  horizontally on a phone).
- `FilterBar` — search input (debounced 300 ms), filter selects, active-filter chips, "مسح الفلاتر".
- `EmptyState` — line-art icon in a brand-tinted circle, title, one sentence, primary action.
- `ErrorState` — cause + "إعادة المحاولة".
- `ConfirmDialog` — destructive variant shows the delete-preview counts and needs a typed confirmation for
  student/course/exam deletes.
- `CourseCard` — accent edge, subject chip, title, progress ring, lesson count, continue button.
- `ProgressRing` — SVG, animated once, `role="img"` with an Arabic label.
- `Countdown` — for the next live session and exam.
- `StatusBadge` — one component mapping every status enum to its Arabic label + colour, so wording is
  identical everywhere (حاضر / غائب / متأخر / بعذر / غير محدد · نشط / قيد الانتظار / منتهي / موقوف ·
  قادم / متاح الآن / انتهى / مسودة).
- `AttendanceStatusGroup` — the 4 one-tap buttons + note.
- `QuestionImage` — zoomable (pinch/wheel/double-tap, and a fullscreen button), white plate, skeleton, retry
  on a failed signed URL.
- `AnswerChoice` — big A/B/C/D target (min 56 px tall), selected/hover/focus states.
- `QuestionNavigator` — grid of numbers: answered (filled brand), current (ring), unanswered (outline).
- `ExamTimer` — sticky, `tabular-nums`; neutral → amber at 5 min → red at 1 min, with one soft chime and an
  `aria-live="polite"` announcement at 5 min and 1 min.
- `PointsBadge`, `RankPodium` (top 3), `PointHistoryItem` — the only gold-accented components.
- `UploadDropzone` — multi-select, per-file rows with compressed size and progress.
- `AnswerKeyInput` — LTR monospace textarea with a live parse preview ("تم قراءة 40 إجابة لـ 40 سؤال").

---

## 7. Layout shells

**Student (mobile-first).**

```
< 768px                                  ≥ 1024px
┌──────────────────────────┐             ┌───────┬────────────────────────────┐
│ ☰  [logo] Talent   🔔 👤 │  56px       │ side  │  top bar: title · 🔔 · 👤  │
├──────────────────────────┤             │ rail  ├────────────────────────────┤
│                          │             │ 240px │                            │
│        content           │             │       │   content (max-w 1200px)   │
│      (16px gutters)      │             │ nav   │                            │
│                          │             │ items │                            │
├──────────────────────────┤             │       │                            │
│ 🏠  📚  🎥  📝  🏆      │  64px       │ ───── │                            │
│ الرئيسية الكورسات ...    │  bottom nav │ خروج  │                            │
└──────────────────────────┘             └───────┴────────────────────────────┘
```

Bottom nav holds the 5 most-used items (الرئيسية · الكورسات · الحصص · الامتحانات · النقاط); الدروس، الجدول،
الإشعارات، الملف الشخصي live in the ☰ sheet and the avatar menu. It respects
`padding-bottom: env(safe-area-inset-bottom)`. The exam runner renders **outside** this shell.

**Admin.** Collapsible sidebar (264 px → 72 px icons-only, remembered per user); becomes an overlay sheet
below 1024 px. Sidebar groups: نظرة عامة · **الطلاب**، المجموعات · **الكورسات** · **الحصص**، الحضور ·
**الامتحانات** · التقارير، الإعلانات · الإعدادات. Top bar: breadcrumb, global search (`⌘K`), theme toggle,
account menu. Editing happens in **drawers**, so the table behind keeps its scroll position and filters.

---

## 8. Key screens

### 8.1 Login
```
┌───────────────────────────────┬──────────────────────────────┐
│                               │                              │
│         ◎ [logo]              │   deep navy panel            │
│      Talent Academy           │   subtle diagonal light      │
│   منصة الدبلومة الأمريكية      │                              │
│                               │   "استعد لـ EST · SAT · ACT"  │
│  كود الطالب أو بريد الإدارة    │   one line of reassurance    │
│  [ TA-000123        ] LTR     │                              │
│  كلمة المرور                   │   (hidden < 900px)           │
│  [ •••••••••     👁 ]         │                              │
│  ☐ تذكرني                     │                              │
│  [    تسجيل الدخول    ]       │                              │
│  نسيت كلمة المرور؟ تواصل معنا  │                              │
└───────────────────────────────┴──────────────────────────────┘
```
One field for both identities. Errors appear above the button as one Arabic message that never says whether
the account exists. The WhatsApp link comes from settings. No demo credentials, ever.

### 8.2 Student dashboard
```
┌────────────────────────────────────────────────────────────────┐
│  صباح الخير، محمد 👋          G12 · طالب أكاديمية · TA-000123  │
├──────────────────────┬─────────────────────┬───────────────────┤
│ الحصة القادمة   LIVE │ الامتحان القادم      │ نقاطي        🏆   │
│ SAT Math — الجبر     │ EST English Unit 3  │  ⬤ 482 نقطة      │
│ ⏱ تبدأ خلال 02:14:31 │ الخميس 7:00م · 40د   │  إجمالي كل الكورسات│
│ [ دخول الحصة ]       │ [ التفاصيل ]         │                   │
│                      │                     │  SAT Math   #4 ▸ │
│                      │                     │  EST English #1 ▸│
├──────────────────────┴─────────────────────┴───────────────────┤
│ كورساتي                                        عرض الكل ‹      │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│ │ ◔ 62%    │ │ ◔ 25%    │ │ ◔ 0%     │   progress rings        │
│ │ SAT Math │ │ EST Eng  │ │ ACT Sci  │                        │
│ │ 12/19 درس│ │ 4/16 درس │ │ 0/9 درس  │                        │
│ │ [أكمل]   │ │ [أكمل]   │ │ [ابدأ]   │                        │
├────────────────────────────────────────────────────────────────┤
│ حضوري 92% ▓▓▓▓▓░ │ متوسط الامتحانات 78% │ دروس مكتملة 16      │
└────────────────────────────────────────────────────────────────┘
```
One request (`/me/dashboard`), one skeleton that matches this layout. On mobile the three focus cards stack;
the live card comes first and turns red-accented with a pulsing dot when a session is live. An external
student whose subscription lapsed sees a single amber panel with the reason and a WhatsApp button, in place
of the course grid.

**Points card is per course, not one number (Q9b).** `total_points` (482) is still the academy-wide sum shown
as the headline, but rank is meaningless without a course — a student ranks differently in each course they're
in — so the card lists one row per enrolled course (`{course_title} #{rank}`), each tapping through to that
course's leaderboard tab (§8.4). Two courses fit before the card scrolls; a "+2 أكثر" chip appears past that.

### 8.3 Exam runner (`/exams/[id]/take`) — the most important screen
```
┌────────────────────────────────────────────────────────────────┐
│ SAT Math — Unit 3      ●●●○○ 18/40 مُجاب      ⏱ 24:13   [تسليم]│ sticky, 64px
├───────────────────────────────────────────┬────────────────────┤
│  ┌──────────────────────────────────────┐ │ الأسئلة            │
│  │  Q18 · 1 pt · Algebra · Medium   [⛶] │ │ ┌──┬──┬──┬──┬──┐  │
│  │ ┌──────────────────────────────────┐ │ │ │1 │2 │3 │4 │5 │  │
│  │ │                                  │ │ │ ├──┼──┼──┼──┼──┤  │
│  │ │     question image (LTR)         │ │ │ │6 │7 │8 │9 │10│  │
│  │ │     white plate, zoomable        │ │ │ └──┴──┴──┴──┴──┘  │
│  │ └──────────────────────────────────┘ │ │  ▣ مُجاب           │
│  │  ┌────────────────────────────────┐  │ │  ▢ بدون إجابة      │
│  │  │ A                              │  │ │  ◎ السؤال الحالي   │
│  │  ├────────────────────────────────┤  │ │                    │
│  │  │ B          ✓ selected          │  │ │ 💾 حُفظ تلقائيًا    │
│  │  ├────────────────────────────────┤  │ │                    │
│  │  │ C                              │  │ │ ⚠ تحذير 1/2        │
│  │  ├────────────────────────────────┤  │ │                    │
│  │  │ D                              │  │ │                    │
│  │  └────────────────────────────────┘  │ │                    │
│  └──────────────────────────────────────┘ │                    │
│        [ ‹ السابق ]        [ التالي › ]   │                    │
└───────────────────────────────────────────┴────────────────────┘
```
- **No app shell, no nav** — only the exam. One question at a time on mobile (swipe + buttons); on desktop
  the same single-question layout with the navigator docked on the side, because a long scroll makes students
  miss questions.
- **Answer-sheet mode** drops the image plate and shows compact numbered rows of A/B/C/D bubbles, 2 columns on
  desktop and 1 on mobile.
- Timer: neutral → amber under 5:00 → red under 1:00 (colour is never the only signal: the label changes to
  "أقل من 5 دقائق").
- **Warning dialog** (first violation): amber, "تحذير — لا تغادر صفحة الامتحان. الخروج مرة أخرى سيقفل
  المحاولة." with one "فهمت" button.
- **Lock screen** (second): replaces everything — red lock icon, "تم إغلاق المحاولة", "إجاباتك محفوظة. تواصل
  مع الإدارة لإعادة الفتح", and a WhatsApp button. No way back into the questions.
- Submit opens a confirm dialog listing the unanswered question numbers.

### 8.4 Points & leaderboard
```
┌────────────────────────────────────────────────────────────────┐
│ نقاطي           482 نقطة (كل الكورسات)                        │
├────────────────────────────────────────────────────────────────┤
│ الترتيب في:  [ SAT Math ▾ ]     ← course selector, pill tabs    │
│              on mobile it's a select; ≥3 courses on desktop     │
│              render as pill tabs instead                        │
├────────────────────────────────────────────────────────────────┤
│              🥈 أحمد            🥇 سارة                        │
│              210                🏆 260      🥉 محمد    190      │
│           ┌──────────┐      ┌──────────┐  ┌──────────┐         │
│           │          │      │          │  │          │         │
│           └──────────┘      └──────────┘  └──────────┘         │
├────────────────────────────────────────────────────────────────┤
│ #4  👤 محمد أحمد (أنت)                            165 نقطة ▍   │ ← pinned, sticky
├────────────────────────────────────────────────────────────────┤
│ #5  👤 ...                                         150 نقطة    │
│ #6  👤 ...                                         140 نقطة    │
├────────────────────────────────────────────────────────────────┤
│ سجل النقاط                                                      │
│ +7  حضور في الموعد — حصة SAT Math                  منذ يومين   │
│ +10 امتحان EST Unit 2 — 85%                        منذ 4 أيام   │
└────────────────────────────────────────────────────────────────┘
```
**Leaderboard is scoped to one course at a time (Q9b)**, selected by the pill tabs / select above the podium
— defaulting to the course the student came from (dashboard rank link) or their first enrolled course. The
podium, tie-aware full list and the student's pinned row are all *within that course*, and switching the
selector re-fetches `/me/leaderboard?course_id=`. The point-history list at the bottom stays global (every
event across every course, each row already names its source), since a student's activity feed is naturally
one timeline. **Names only, never the student code** (Q9) — `display_name` is the only identifier shown to
students anywhere on this page, including the pinned "you" row.

### 8.5 Admin students (the pattern for every admin list)
```
┌─────────────────────────────────────────────────────────────────────┐
│ الطلاب                            [استيراد Excel] [+ طالب جديد]     │
│ [🔍 بحث بالاسم أو الكود] [الصف ▾][النوع ▾][الاشتراك ▾][المجموعة ▾]  │
│ فلاتر: G12 ✕  خارجي ✕                                مسح الفلاتر    │
├─────────────────────────────────────────────────────────────────────┤
│ ☐ │ الطالب          │ الكود    │ الصف │ النوع  │ الاشتراك│ نقاط │ ⋮ │
│ ☐ │ 👤 محمد أحمد    │ TA-00012 │ G12  │ أكاديمي│ ● نشط  │ 482  │ ⋮ │
│ ☑ │ 👤 سارة محمود   │ TA-00034 │ G11  │ خارجي  │ ● منتهي│ 610  │ ⋮ │
├─────────────────────────────────────────────────────────────────────┤
│  ▸ 2 محدد: [إضافة لمجموعة][تسجيل في كورس][تفعيل][إيقاف][حذف]        │  floating
│                                         ‹ 1 2 3 › من 248 طالب        │
└─────────────────────────────────────────────────────────────────────┘
```
Row click opens the student **drawer** (info · الكورسات · المجموعات · الأمان) with a link to the full report
page. Under 768 px each student becomes a card with name, code, two badges and an action menu.

### 8.6 Attendance sheet — built for speed
```
┌─────────────────────────────────────────────────────────────┐
│ ‹ SAT Math — حصة السبت      السبت 21 سبتمبر 6:00م           │
│ حاضر 18 · متأخر 3 · غائب 2 · بعذر 1 · غير محدد 4            │
│ [🔍 بحث]                    [تعليم الباقي غياب (إنهاء)]      │
├─────────────────────────────────────────────────────────────┤
│ 👤 محمد أحمد   TA-00012  │ [حاضر][متأخر][غائب][بعذر] │ 📝  │
│    دخل 6:03م ✓ تلقائي     │   ▲ selected                    │
│ 👤 سارة محمود  TA-00034  │ [حاضر][متأخر][غائب][بعذر] │ 📝  │
└─────────────────────────────────────────────────────────────┘
```
Each tap saves immediately (optimistic, with a toast on failure and a revert). Buttons are 44 px tall and full
width on mobile. Students who joined from the platform show a "تلقائي" chip with the join time; an admin
override keeps that chip and adds "عُدّل بواسطة الإدارة".

### 8.7 Exam builder
Three steps as tabs, with a readiness banner at the top ("الأسئلة 40 · مفتاح الإجابات ✓ · جاهز للنشر"):
**الإعدادات** (course/group, mode, timing, attempts, pass mark) → **الأسئلة** (dropzone with per-file
compression progress; a 4-column grid of question thumbnails with topic/difficulty/points inline and a
correct-answer letter chip) → **مفتاح الإجابات** (LTR textarea + live parse preview + apply). Publishing is
disabled with a tooltip listing the question numbers that are missing a correct answer. Once attempts exist, a
blue banner explains that questions and scoring are frozen, and those controls are disabled rather than hidden.

---

## 9. States every page must have

1. **Skeleton** shaped like the real content (never a spinner over the whole page).
2. **Empty** — icon, one sentence in the academy's voice, and the action that fixes it
   (admin: "لسه مفيش طلاب — أضف طالب أو استورد من Excel"; student: "لسه مفيش امتحانات. أي امتحان جديد هيظهر هنا").
3. **Error** — what failed + "إعادة المحاولة"; a 403/404 on a student route shows "المحتوى ده مش متاح لحسابك".
4. **Blocked** (external students) — amber panel with the reason and a WhatsApp button.
5. **Offline/stale** — a top strip "لا يوجد اتصال — آخر تحديث 10:32" ; during an exam it says explicitly
   that this is **not** counted as leaving the page.
6. **Toasts** for every mutation (success 3 s, error sticky with retry) and **confirm dialogs** for every
   destructive action.
7. **Optimistic updates** for one-tap actions (attendance, lesson complete, mark read), with rollback.

---

## 10. Accessibility

Target: **WCAG 2.2 AA**. Body text ≥4.5:1, large text and UI borders ≥3:1 — including every badge, both
themes, all 7 course accents (validated with a script in CI).
Visible focus everywhere: `outline: 2px solid var(--ring); outline-offset: 2px` (never `outline: none`).
Full keyboard support: skip-to-content link, logical tab order, Escape closes dialogs/drawers, arrow keys in
the question navigator and attendance rows. Radix handles focus traps and `aria-modal`.
Every icon-only button has an `aria-label`; status is never colour-only (icon + Arabic word);
form errors are tied with `aria-describedby` and announced; the timer announces at 5:00 and 1:00 politely;
toasts use a polite live region. Tap targets ≥44×44 with ≥8 px between them.
Tested with NVDA + Firefox in Arabic, and with iOS VoiceOver on the exam runner.

---

## 11. Assets and performance

- **Logo (confirmed, ARCHITECTURE.md A18):** `talent-logo.png` from the prototype is a 240 px screenshot crop
  with artefacts on its edges. Until the original arrives, use a cleaned, centred crop exported at 1x/2x/3x
  plus a monochrome white version for the navy panel and a 32/180 px favicon set. The logo lockup is a
  component (`<Brandmark size compact />`), never an inline `<img>`, so swapping in the final file later is a
  one-file change.
- **Icons:** `lucide-react`, imported per icon (tree-shaken), 20 px in UI and 24 px in empty states,
  `stroke-width: 1.75`.
- **Illustrations:** no stock art. Empty states use a large line icon inside a brand-tinted circle, so nothing
  extra is downloaded.
- **Budget per route:** ≤ 180 KB of JS gzipped (first load). Server components by default; `"use client"` only
  where there is interaction. Heavy pieces (exam runner, builder, DataTable, image zoom) are dynamically
  imported. Fonts are self-hosted and preloaded with `display: swap`; no external font requests at runtime.
- **Images:** `next/image` for the logo and covers. Question images are plain `<img>` with signed URLs
  (`next/image` would need R2 in `remotePatterns` and would proxy bytes through the frontend for no benefit),
  `loading="lazy"` beyond the first, plus explicit width/height to avoid layout shift.
- Targets on a mid-range Android over 4G: LCP < 2.5 s, CLS < 0.05, INP < 200 ms on the exam runner.
