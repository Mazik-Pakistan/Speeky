# Speeky — Landing Page + Auth Pages

Next.js App Router, TypeScript, Tailwind. No shadcn/ui, no Radix — all
UI primitives are hand-built. Palette, type, and logo match the actual
product screens (dashboard, mission select, AI practice session) that
were shared as reference, so the marketing site and the app now look
like one product.

## Routes

- `/` — landing page
- `/login` — email + password
- `/signup` — first name, last name, email, password, confirm password

Navbar and every CTA on the landing page link to `/login` and `/signup`.

## Folder structure

```
app/
  layout.tsx           root layout, fonts (Manrope + Libre Caslon Text)
  page.tsx              landing page, assembles all sections
  globals.css           design tokens — single source of truth for color
  login/page.tsx
  signup/page.tsx
components/
  common/
    SectionTitle.tsx
    Footer.tsx
  landing/
    Navbar.tsx
    HeroSection.tsx
    WhySpeeky.tsx
    FeatureCard.tsx
    CoreFeatures.tsx
    HowItWorks.tsx
    StatsCard.tsx
    ProgressAnalytics.tsx
    TestimonialCard.tsx
    Testimonials.tsx
    FAQSection.tsx
    CTASection.tsx
  auth/
    AuthShell.tsx        shared split-screen layout for login/signup
    LoginForm.tsx
    SignupForm.tsx
  ui/
    button.tsx           custom Button (no shadcn/Radix)
    accordion.tsx         custom single-open accordion
    input.tsx             custom text/password input w/ inline error
lib/
  types.ts
  mock-data.ts
  utils.ts
public/
  logo-full.png          icon + wordmark, transparent bg (nav, auth, footer)
  logo-icon.png           icon mark only, transparent bg
tailwind.config.ts
```

## Design tokens (updated to match the real product)

Pulled from the four Stitch screens shared (home dashboard, choose your
mission, AI practice session, main marketing screen) — all four use the
same palette, so this is the authoritative brand system going forward:

- Primary: `#00246E` (Royal Blue) — buttons, active states, links
- Accent: `#B52424` (Crimson) — small AI highlights, expressive accents
- Headings: Libre Caslon Text (serif) — `font-serif` in Tailwind
- Body/UI: Manrope — `font-sans` in Tailwind (default)
- Everything still goes through semantic tokens (`bg-primary`,
  `text-foreground`, etc.) — no raw hex anywhere in components.

## Auth forms

- **Signup**: First name + Last name are separate inputs for a friendlier
  form, combined into one `fullName` string only at submit time — that's
  the only shape sent onward. Email format, password length (8+), and
  password/confirm-password match are all validated inline, as soon as a
  field is touched (not just on submit).
- **Login**: email + password, same inline validation pattern.
- Both forms take an optional `onSubmit` prop
  (`(values) => Promise<void> | void`). Without one they just
  `console.log` the payload — swap that prop for the real API call
  your teammate builds; no other wiring needed.
- No social login buttons were added since they weren't requested — easy
  to add later inside `AuthShell` if needed.

## Assumptions / integration notes

- No shadcn/ui or Radix dependency anywhere, including the new auth
  pages. If your host project already has its own `Button` / `Accordion`
  / `Input` in `components/ui/`, prefer those and delete these three
  files instead.
- `app/globals.css` is the single source of truth for color — merge
  instead of overwriting if the host app already has its own.
- No backend, auth logic, or global state — UI only, ready to wire up.
- All content in `lib/mock-data.ts` is placeholder copy and should be
  replaced with real copy before launch.
- Dark mode works automatically via the `.dark` class and CSS
  variables; no component hardcodes a dark color.

## Testing note

This environment has no network access, so a real `npm install` /
`next build` could not be run here (`npm install` fails with a 403 from
the sandbox's egress proxy). Verified instead with the TypeScript
compiler directly against every file (using minimal stand-in type
declarations for the packages that couldn't be installed) to catch
real syntax/logic errors, plus a manual review pass of every changed
file. Please run `npm install && npm run build` on your end as the
final check — real `next`/`react` types will catch anything a
stand-in shim can't.
