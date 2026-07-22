import Link from "next/link";
import Image from "next/image";
import type { ReactNode } from "react";

interface AuthShellProps {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  footer: ReactNode;
  legalNote?: ReactNode;
}

const DEFAULT_LEGAL_NOTE = (
  <p>
    By continuing you agree to Speeky&apos;s{" "}
    <Link href="/terms" className="font-medium text-foreground hover:text-primary">
      Terms
    </Link>{" "}
    and{" "}
    <Link href="/privacy" className="font-medium text-foreground hover:text-primary">
      Privacy Policy
    </Link>
    .
  </p>
);

/**
 * Shared shell for /login, /signup, /forgot-password, and /reset-password.
 * Keeps every auth page visually identical: logo, headline, supporting
 * text, form, footer note. Pass `legalNote` to override the default
 * "By continuing..." line for a specific page.
 */
export function AuthShell({
  eyebrow,
  title,
  description,
  children,
  footer,
  legalNote,
}: AuthShellProps) {
  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      {/* Branding panel */}
      <div className="relative hidden flex-col overflow-hidden bg-primary px-12 py-10 text-primary-foreground lg:flex lg:w-1/2">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_50%_at_20%_0%,hsl(var(--accent)/0.35)_0%,transparent_60%)]"
        />

        <div className="relative z-10 flex flex-1 flex-col items-center justify-center gap-10 text-center">
          <Link href="/" className="inline-flex items-center">
            <Image
              src="/logo-full.png"
              alt="Speeky"
              width={213}
              height={239}
              className="h-24 w-auto brightness-0 invert"
            />
          </Link>

          <div className="flex max-w-md flex-col items-center gap-4">
            <p className="font-serif text-3xl leading-snug">
              &ldquo;Practicing out loud with the AI made the real interview
              feel familiar instead of terrifying.&rdquo;
            </p>
            <p className="text-sm text-primary-foreground/70">
              Amara K. &middot; MBA Candidate
            </p>
          </div>
        </div>

        <p className="relative z-10 text-center text-xs text-primary-foreground/60">
          &copy; {new Date().getFullYear()} Speeky. Built for Mazik Global.
        </p>
      </div>

      {/* Form panel */}
      <div className="flex w-full flex-1 flex-col justify-center px-6 py-12 sm:px-12 lg:w-1/2 lg:px-16">
        <div className="mx-auto flex w-full max-w-sm flex-col gap-8">
          <Link href="/" className="inline-flex items-center lg:hidden">
            <Image
              src="/logo-full.png"
              alt="Speeky"
              width={142}
              height={159}
              className="h-9 w-auto"
            />
          </Link>

          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium text-primary">
              {eyebrow}
            </span>
            <h1 className="font-serif text-3xl font-semibold tracking-tight text-foreground">
              {title}
            </h1>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>

          {children}

          <div className="flex flex-col gap-4 border-t border-border pt-6 text-center text-xs text-muted-foreground">
            {footer}
            {legalNote ?? DEFAULT_LEGAL_NOTE}
          </div>
        </div>
      </div>
    </div>
  );
}
