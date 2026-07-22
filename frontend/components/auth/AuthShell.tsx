"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { TESTIMONIALS } from "@/lib/mock-data";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";
import { LegalModal } from "@/components/common/LegalModal";

interface AuthShellProps {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
  footer: ReactNode;
  legalNote?: ReactNode;
}

export function AuthShell({
  eyebrow,
  title,
  description,
  children,
  footer,
  legalNote,
}: AuthShellProps) {
  const [quoteIndex, setQuoteIndex] = React.useState(0);
  const [fade, setFade] = React.useState(true);
  const [legalType, setLegalType] = React.useState<"terms" | "privacy" | null>(
    null,
  );

  React.useEffect(() => {
    const interval = setInterval(() => {
      setFade(false);

      setTimeout(() => {
        setQuoteIndex((prev) => (prev + 1) % TESTIMONIALS.length);
        setFade(true);
      }, 500);
    }, 8000);

    return () => clearInterval(interval);
  }, []);

  const currentQuote = TESTIMONIALS[quoteIndex];

  const defaultLegalNote = (
    <p>
      By continuing you agree to Speeky&apos;s{" "}
      <button
        type="button"
        onClick={() => setLegalType("terms")}
        className="font-medium text-foreground hover:text-primary"
      >
        Terms
      </button>{" "}
      and{" "}
      <button
        type="button"
        onClick={() => setLegalType("privacy")}
        className="font-medium text-foreground hover:text-primary"
      >
        Privacy Policy
      </button>
      .
    </p>
  );

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      {/* Changed text-primary-foreground to text-white to enforce visibility on dark backgrounds */}
      <div className="animate-gradient-shift relative hidden flex-col overflow-hidden bg-gradient-to-br from-primary via-[#1D3B8A] to-[#00113D] bg-[length:200%_200%] px-12 py-10 text-white lg:flex lg:w-1/2">
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

          <div
            className={cn(
              "flex max-w-md flex-col items-center gap-4 transition-opacity duration-500 ease-in-out",
              fade ? "opacity-100" : "opacity-0",
            )}
          >
            <p className="font-serif text-3xl leading-snug text-white">
              &ldquo;{currentQuote.quote}&rdquo;
            </p>
            <p className="text-sm text-white/80">
              {currentQuote.name} &middot; {currentQuote.role}
            </p>
          </div>
        </div>
        <p className="relative z-10 text-center text-xs text-white/60">
          &copy; {new Date().getFullYear()} Speeky. Built for Mazik Global.
        </p>
      </div>

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
            <span className="text-sm font-medium text-primary">{eyebrow}</span>
            <h1 className="font-serif text-3xl font-semibold tracking-tight text-foreground">
              {title}
            </h1>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
          {children}
          <div className="flex flex-col gap-4 border-t border-border pt-6 text-center text-xs text-muted-foreground">
            {footer}
            {legalNote ?? defaultLegalNote}
          </div>
        </div>
      </div>

      <LegalModal
        open={!!legalType}
        onClose={() => setLegalType(null)}
        type={legalType}
      />
    </div>
  );
}
