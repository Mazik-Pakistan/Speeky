# Speeky — Frontend

Next.js 14 App Router, TypeScript, Tailwind. All UI primitives are hand-built
(no shadcn/ui, no Radix). Talks to the FastAPI backend in `clone_backend/backend`
over httpOnly cookies — see [Backend integration](#backend-integration).

## Routes

**Public**
- `/` — landing page (redirects to `/dashboard` if already logged in)
- `/login`, `/signup` (email OTP verification), `/forgot-password`, `/reset-password`
- `/terms`, `/privacy`

**Dashboard** (all require login — redirect to `/login` if not authenticated)
- `/dashboard` — home (streak, mastery, recent scenarios)
- `/dashboard/explore` — feature hub: links into every practice mode below
- `/dashboard/assessment` — baseline assessment (intro → 5 questions → results); also
  handles the skip-assessment flow
- `/dashboard/coaching`, `/dashboard/coaching/[scenario]` — Workplace English Coach
  (5 scenarios, text or roleplay, graded on tone/clarity/effectiveness).
  Gated on a completed assessment.
- `/dashboard/conversation`, `/dashboard/conversation/[sessionId]` — AI Conversation
  Practice (topic chat, grammar correction chips, TTS playback with a browser-native
  fallback if the server voice model isn't installed). Gated on a completed assessment.
- `/dashboard/interview-coach`, `/dashboard/interview-coach/[sessionId]`,
  `/dashboard/interview-coach/reviews/[shareId]` — mock interviews (standard, panel,
  case study, multi-round), pause/resume/break, peer-review sharing + comments.
  Not gated.
- `/dashboard/resume-jd` — resume upload + job description intake + mismatch check.
  Not gated.
- `/dashboard/profile` — profile info + avatar, learning goal, baseline assessment
  status/retake, performance memory, privacy & consent, conversation memory,
  code-switch coaching settings, password reset, account deletion.

## Backend integration

`NEXT_PUBLIC_APP_API_URL` (in `.env`) points at the FastAPI backend
(`clone_backend/backend`). Auth is httpOnly-cookie based and cross-origin, so:

- There's no client-readable "am I logged in" flag — every auth check is a real
  `GET /users/me` call (see `contexts/AuthContext.tsx`).
- `lib/api.ts`'s `api()` wrapper silently refreshes the access token on a 401 and
  retries once, sharing a single in-flight refresh across concurrent requests
  (the backend revokes all tokens if a stale refresh token is reused, so this can't
  be done per-request). A refresh that still fails clears auth state via a
  `speeky:session-expired` window event, which `AuthContext` listens for.
- Feature-access gating (Coaching, Conversation) reads `GET /assessment/access`
  via `contexts/AssessmentContext.tsx`, scoped to the dashboard layout.

Backend endpoints without a frontend-buildable path are flagged with
`TODO(backend)` comments at the top of the relevant `lib/*.ts` file (currently:
learning goal, privacy consent, and code-switch settings all persist to
`localStorage` pending real backend fields/endpoints).

**Known backend-side gaps** (not fixable from this folder):
- No real microphone/voice input pipeline wired to any endpoint — the separate
  LiveKit speech-to-text agent (`clone_backend/backend/speech-to-text/`) isn't
  connected. All practice flows use typed text.
- No GET endpoint to fetch a shared interview's transcript, so the peer-review
  page shows comments only.
- No GET-session (Interview Coach) or list-JDs (Resume/JD) endpoints, so those
  two lose in-progress state on a hard reload (Coaching, Conversation, and the
  résumé list all persist correctly).
- No Google/Apple OAuth routes — those signup buttons are shown disabled.

## Folder structure

```
app/
  layout.tsx, error.tsx, global-error.tsx, not-found.tsx, providers.tsx
  page.tsx                      landing page
  globals.css                   design tokens — single source of truth for color
  login/, signup/, forgot-password/, reset-password/, terms/, privacy/
  dashboard/
    layout.tsx                  auth guard + sidebar + AssessmentProvider
    page.tsx                    home
    explore/, assessment/, profile/
    coaching/, conversation/, interview-coach/, resume-jd/
components/
  common/        Footer, SectionTitle, LegalDocument (shared terms/privacy shell)
  landing/       Navbar, HeroSection, WhySpeeky, CoreFeatures, HowItWorks,
                 ProgressAnalytics, Testimonials, FAQSection, CTASection,
                 LandingAuthRedirect
  auth/          AuthShell, LoginForm, SignupForm (credentials → goal → OTP),
                 ForgotPasswordForm, ResetPasswordForm
  dashboard/     Sidebar, AssessmentReminderBanner, profile/ (9 section components)
  ui/            button, input, textarea, checkbox, switch, modal, accordion
                 — no shadcn/Radix dependency
contexts/
  AuthContext.tsx          session state (user, isLoading, logout)
  AssessmentContext.tsx    feature-access gating state, dashboard-scoped
lib/
  api.ts                   fetch wrapper: auth cookies, error parsing, silent refresh
  auth.ts, user.ts         auth + profile/avatar/account-deletion calls
  assessment.ts            baseline assessment + gating + re-assessment calls
  coaching.ts, conversation.ts, interviewCoach.ts, resumeJd.ts, sessionMemory.ts
  goals.ts, consent.ts, code-switch.ts    localStorage-backed prefs (see TODO(backend))
  validation.ts            shared email-domain / password / name rules (mirrors backend)
  dashboard-data.ts, mock-data.ts, terms-content.ts, privacy-content.ts   placeholder copy
  types.ts, utils.ts
public/
  logo-full.png, logo-icon.png
tailwind.config.ts
```

## Design tokens

- Primary: `#00246E` (Royal Blue) — buttons, active states, links
- Accent: `#B52424` (Crimson) — highlights, expressive accents
- Headings: Libre Caslon Text (serif) — `font-serif` in Tailwind
- Body/UI: Manrope — `font-sans` (default)
- Everything goes through semantic tokens (`bg-primary`, `text-foreground`, etc.)
  defined once in `app/globals.css` — never a raw hex in a component.
- Dark mode works via the `.dark` class and the same CSS variables.

## Auth

- **Signup** is three steps: credentials → mandatory learning-goal selection →
  email OTP verification. The backend creates no account until the emailed code
  is verified (`POST /auth/signup` only queues it and sends the code). Resend is
  gated client-side: 60s cooldown, 3 resends max per attempt.
- **Login**: email + password. Email is restricted to `@gmail.com` / `@outlook.com`
  and passwords require upper/lower/digit/special-char (see `lib/validation.ts`) —
  these mirror the backend's Pydantic validators, not just cosmetic client rules.
- **Password reset**: request → emailed link with a token → set new password.
  The request step always shows the same "check your inbox" confirmation
  regardless of whether the email is registered (anti-enumeration, matches
  backend behavior).

## Testing

No automated test suite yet. Every feature in this app has been verified with a
real browser against the live backend (Playwright, driven ad hoc — not checked
into the repo). Minimum before considering a change done:

```
npx tsc --noEmit
npx next build
```

`next build` also runs Next's type/lint pass and is the only way `app/error.tsx`
actually activates (it's bypassed in `next dev`) — use `next start` after building
if you need to test error boundaries or want dev-mode-vs-prod parity.
