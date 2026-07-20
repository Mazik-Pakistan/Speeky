"use client";

import * as React from "react";
import { KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { forgotPassword } from "@/lib/auth";
import { useAuth } from "@/contexts/AuthContext";
import { maskEmail } from "@/lib/utils";

export function SecuritySection() {
  const { user } = useAuth();
  const [status, setStatus] = React.useState<"idle" | "submitting" | "sent">("idle");
  const [error, setError] = React.useState<string | null>(null);

  if (!user) return null;

  async function handleSendResetLink() {
    setError(null);
    setStatus("submitting");
    try {
      await forgotPassword(user!.email);
      setStatus("sent");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      setStatus("idle");
    }
  }

  return (
    <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-primary">
          <KeyRound className="h-4 w-4" aria-hidden="true" />
        </span>
        <div className="flex flex-1 flex-col gap-1">
          <h2 className="text-sm font-semibold text-foreground">Password</h2>
          <p className="text-sm text-muted-foreground">
            For your security, we don&apos;t change passwords directly here.
            We&apos;ll email a secure reset link to your registered address.
          </p>
        </div>
      </div>

      {status === "sent" ? (
        <p className="mt-4 rounded-xl bg-secondary px-4 py-3 text-sm text-secondary-foreground">
          Check your inbox — if <strong>{maskEmail(user.email)}</strong> is
          registered, a reset link is on its way.
        </p>
      ) : (
        <>
          {error ? <p className="mt-4 text-sm text-danger">{error}</p> : null}
          <Button
            type="button"
            variant="outline"
            size="sm"
            loading={status === "submitting"}
            onClick={handleSendResetLink}
            className="mt-4"
          >
            Send Password Reset Link
          </Button>
        </>
      )}
    </div>
  );
}
