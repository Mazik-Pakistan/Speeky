import fs from "node:fs";
import path from "node:path";
import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Dashboard routes are auth-gated; without a session they render an empty shell and
// every assertion below would be meaningless. Inject the QA session cookie instead of
// driving the login form, so the audit tests the UI rather than the auth flow.
// Regenerate e2e/.auth.json (gitignored) by running, from backend/:
//   PYTHONPATH=. ./.venv/Scripts/python.exe scripts/make_qa_auth.py
// Tear the QA user back down with the same script's --cleanup flag.
const { token } = JSON.parse(
  fs.readFileSync(path.join(__dirname, ".auth.json"), "utf-8"),
) as { token: string };

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    { name: "access_token", value: token, domain: "localhost", path: "/" },
  ]);
});

/**
 * UI regression + accessibility audit.
 *
 * Guards the redesign against the two failure modes that matter: a visual/DS change
 * silently breaking a page (console errors, overflow, missing content), and a
 * styling change regressing accessibility (contrast, names, roles).
 */

const PUBLIC_PAGES = ["/", "/login", "/signup"];
const APP_PAGES = [
  "/dashboard",
  "/dashboard/assessment",
  "/dashboard/progress",
  "/dashboard/rewrite",
  "/dashboard/explore",
  "/dashboard/profile",
  "/dashboard/pronunciation",
  "/dashboard/accent-assessment",
  "/dashboard/public-speaking",
  "/dashboard/conversation",
  "/dashboard/interview-coach",
  "/dashboard/coaching",
  "/dashboard/resume-jd",
];
const ALL_PAGES = [...PUBLIC_PAGES, ...APP_PAGES];

const BREAKPOINTS = [
  { name: "mobile", width: 375, height: 812 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "laptop", width: 1280, height: 800 },
  { name: "desktop", width: 1680, height: 1050 },
  { name: "ultrawide", width: 2560, height: 1080 },
];

/** Fatal console errors only — ignore expected 401s from unauthenticated API calls. */
function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    if (/401|403|Unauthorized|Not authenticated|Failed to load resource/i.test(text)) return;
    errors.push(text);
  });
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  return errors;
}

test.describe("pages render without crashing", () => {
  for (const path of ALL_PAGES) {
    test(`renders ${path}`, async ({ page }) => {
      const errors = collectErrors(page);
      const res = await page.goto(path, { waitUntil: "networkidle" });
      expect(res?.status(), `HTTP status for ${path}`).toBeLessThan(400);
      await page.waitForTimeout(800);
      // A React crash boundary or blank body is the real failure signal.
      const bodyText = (await page.locator("body").innerText()).trim();
      expect(bodyText.length, `${path} rendered empty`).toBeGreaterThan(0);
      expect(errors, `console errors on ${path}`).toEqual([]);
    });
  }
});

test.describe("no horizontal overflow at any breakpoint", () => {
  for (const bp of BREAKPOINTS) {
    test(`${bp.name} (${bp.width}px)`, async ({ page }) => {
      await page.setViewportSize({ width: bp.width, height: bp.height });
      for (const path of ALL_PAGES) {
        await page.goto(path, { waitUntil: "networkidle" });
        await page.waitForTimeout(400);
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        // 1px tolerance for sub-pixel rounding.
        expect(overflow, `${path} overflows horizontally at ${bp.width}px`).toBeLessThanOrEqual(1);
      }
    });
  }
});

test.describe("accessibility (axe) — light and dark", () => {
  for (const theme of ["light", "dark"] as const) {
    test(`no serious/critical violations · ${theme}`, async ({ page }) => {
      const findings: string[] = [];
      for (const path of ALL_PAGES) {
        await page.goto(path, { waitUntil: "networkidle" });
        await page.evaluate((t) => {
          localStorage.setItem("speeky-theme", t);
          document.documentElement.classList.toggle("dark", t === "dark");
        }, theme);
        await page.waitForTimeout(300);

        const results = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
          .analyze();

        for (const v of results.violations) {
          if (v.impact === "serious" || v.impact === "critical") {
            findings.push(`${path} [${v.impact}] ${v.id}: ${v.nodes.length} node(s)`);
          }
        }
      }
      expect(findings, `axe violations (${theme})`).toEqual([]);
    });
  }
});

test("keyboard: focus is visible and reaches interactive controls", async ({ page }) => {
  await page.goto("/login", { waitUntil: "networkidle" });
  await page.keyboard.press("Tab");
  const focused = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el || el === document.body) return null;
    const s = getComputedStyle(el);
    return { tag: el.tagName, outline: s.outlineStyle, width: s.outlineWidth };
  });
  expect(focused, "Tab moved focus off body").not.toBeNull();
  expect(focused!.outline, "focus ring is drawn").not.toBe("none");
});

test("reduced motion is honoured", async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto("/dashboard/progress", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const longAnimations = await page.evaluate(() =>
    [...document.querySelectorAll("*")].filter((el) => {
      const d = getComputedStyle(el).animationDuration;
      return d && d !== "0s" && parseFloat(d) > 0.05;
    }).length,
  );
  expect(longAnimations, "animations should collapse under reduced motion").toBe(0);
  await ctx.close();
});
