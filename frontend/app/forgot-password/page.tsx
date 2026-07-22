import type { Metadata } from "next";
import Link from "next/link";
import { AuthShell } from "@/components/auth/AuthShell";
import { ForgotPasswordForm } from "@/components/auth/ForgotPasswordForm";

export const metadata: Metadata = {
  title: "Forgot Password — Speeky",
  description: "Reset the password for your Speeky account.",
};

export default function ForgotPasswordPage() {
  return (
    <AuthShell
      eyebrow="Reset your password"
      title="Forgot your password?"
      description="Enter the email on your account and we'll send you a link to reset it."
      footer={
        <p>
          Remembered it after all?{" "}
          <Link href="/login" className="font-medium text-primary hover:text-primary-hover">
            Log in
          </Link>
        </p>
      }
    >
      <ForgotPasswordForm />
    </AuthShell>
  );
}
