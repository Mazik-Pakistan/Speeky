"use client";

import * as React from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, TriangleAlert } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { resetPassword } from "@/lib/auth";
import { PASSWORD_RULE_ERROR, isValidPassword } from "@/lib/validation";

interface ResetPasswordValues {
  password: string;
  confirmPassword: string;
}

function validate(values: ResetPasswordValues) {
  const errors: Partial<Record<keyof ResetPasswordValues, string>> = {};

  if (!values.password) {
    errors.password = "Password is required.";
  } else if (!isValidPassword(values.password)) {
    errors.password = PASSWORD_RULE_ERROR;
  }

  if (!values.confirmPassword) {
    errors.confirmPassword = "Confirm your password.";
  } else if (values.confirmPassword !== values.password) {
    errors.confirmPassword = "Passwords do not match.";
  }

  return errors;
}

/**
 * Sets a new password using the reset token from the emailed link
 * (`/reset-password?token=...`). If the token is missing or the backend
 * rejects it (invalid/expired/already used), shows an error state
 * pointing back to the forgot-password flow instead of a broken form.
 */
export function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [values, setValues] = React.useState<ResetPasswordValues>({
    password: "",
    confirmPassword: "",
  });
  const [touched, setTouched] = React.useState<
    Partial<Record<keyof ResetPasswordValues, boolean>>
  >({});
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [formError, setFormError] = React.useState<string | null>(null);
  const [isSuccess, setIsSuccess] = React.useState(false);

  const errors = validate(values);

  function handleChange(field: keyof ResetPasswordValues, value: string) {
    setValues((prev) => ({ ...prev, [field]: value }));
  }

  function handleBlur(field: keyof ResetPasswordValues) {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setTouched({ password: true, confirmPassword: true });
    setFormError(null);

    if (!token) {
      setFormError("This reset link is invalid or has expired.");
      return;
    }

    const currentErrors = validate(values);
    if (Object.keys(currentErrors).length > 0) {
      return;
    }

    try {
      setIsSubmitting(true);
      await resetPassword(token, values.password);
      setIsSuccess(true);
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

  if (!token) {
    return (
      <div className="flex flex-col items-start gap-4 rounded-2xl border border-border bg-surface p-6">
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-danger/10 text-danger">
          <TriangleAlert className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="flex flex-col gap-1">
          <p className="text-sm font-medium text-foreground">
            Invalid or expired link
          </p>
          <p className="text-sm text-muted-foreground">
            This password reset link is missing or no longer valid. Request
            a new one to continue.
          </p>
        </div>
        <Button href="/forgot-password" size="sm">
          Request New Link
        </Button>
      </div>
    );
  }

  if (isSuccess) {
    return (
      <div className="flex flex-col items-start gap-4 rounded-2xl border border-border bg-surface p-6">
        <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-success/10 text-success">
          <CheckCircle2 className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="flex flex-col gap-1">
          <p className="text-sm font-medium text-foreground">
            Password reset
          </p>
          <p className="text-sm text-muted-foreground">
            Your password has been updated. You can now log in with your
            new password.
          </p>
        </div>
        <Button href="/login" size="sm">
          Go to Login
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
      <Input
        label="New password"
        type="password"
        autoComplete="new-password"
        value={values.password}
        onChange={(event) => handleChange("password", event.target.value)}
        onBlur={() => handleBlur("password")}
        error={touched.password ? errors.password : undefined}
        hint={
          touched.password && !errors.password
            ? undefined
            : "8+ characters, upper + lowercase, a digit, and a special character."
        }
      />

      <Input
        label="Confirm new password"
        type="password"
        autoComplete="new-password"
        value={values.confirmPassword}
        onChange={(event) =>
          handleChange("confirmPassword", event.target.value)
        }
        onBlur={() => handleBlur("confirmPassword")}
        error={touched.confirmPassword ? errors.confirmPassword : undefined}
      />

      {formError ? <p className="text-sm text-danger">{formError}</p> : null}

      <Button type="submit" size="lg" loading={isSubmitting} className="mt-2">
        Reset Password
      </Button>
    </form>
  );
}
