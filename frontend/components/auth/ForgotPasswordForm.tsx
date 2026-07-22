"use client";

import * as React from "react";
import { Mail } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { forgotPassword } from "@/lib/auth";
import { EMAIL_DOMAIN_ERROR, isAllowedEmailDomain } from "@/lib/validation";

interface ForgotPasswordValues {
  email: string;
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate(values: ForgotPasswordValues) {
  const errors: Partial<Record<keyof ForgotPasswordValues, string>> = {};

  if (!values.email.trim()) {
    errors.email = "Email is required.";
  } else if (!EMAIL_PATTERN.test(values.email.trim())) {
    errors.email = "Enter a valid email address.";
  } else if (!isAllowedEmailDomain(values.email)) {
    errors.email = EMAIL_DOMAIN_ERROR;
  }

  return errors;
}

/**
 * Requests a password reset link. The backend always responds 200 to
 * prevent email enumeration, so this always swaps to the same
 * confirmation state on success regardless of whether the address is
 * actually registered.
 */
export function ForgotPasswordForm() {
  const [values, setValues] = React.useState<ForgotPasswordValues>({
    email: "",
  });
  const [touched, setTouched] = React.useState<
    Partial<Record<keyof ForgotPasswordValues, boolean>>
  >({});
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [formError, setFormError] = React.useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = React.useState(false);

  const errors = validate(values);

  function handleChange(value: string) {
    setValues({ email: value });
  }

  function handleBlur() {
    setTouched({ email: true });
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTouched({ email: true });
    setFormError(null);

    const currentErrors = validate(values);
    if (Object.keys(currentErrors).length > 0) {
      return;
    }

    try {
      setIsSubmitting(true);
      await forgotPassword(values.email.trim());
      setIsSubmitted(true);
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "Something went wrong. Please try again.";
      setFormError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isSubmitted) {
    return (
      <div className="flex flex-col items-start gap-4 rounded-2xl border border-border bg-surface p-6">
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-secondary text-primary">
          <Mail className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="flex flex-col gap-1">
          <p className="text-sm font-medium text-foreground">
            Check your inbox
          </p>
          <p className="text-sm text-muted-foreground">
            If an account exists for <strong>{values.email}</strong>,
            we&apos;ve sent a link to reset your password.
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={() => setIsSubmitted(false)}
        >
          Use a different email
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
      <Input
        label="Email"
        type="email"
        autoComplete="email"
        value={values.email}
        onChange={(event) => handleChange(event.target.value)}
        onBlur={handleBlur}
        error={touched.email ? errors.email : undefined}
      />

      {formError ? <p className="text-sm text-danger">{formError}</p> : null}

      <Button type="submit" size="lg" loading={isSubmitting} className="mt-2">
        Send Reset Link
      </Button>
    </form>
  );
}
