import type { Metadata } from "next";
import { Suspense } from "react";
import Link from "next/link";
import { AuthShell } from "@/components/auth/AuthShell";
import { ResetPasswordForm } from "@/components/auth/ResetPasswordForm";

export const metadata: Metadata = {
  title: "Reset Password — Speeky",
  description: "Choose a new password for your Speeky account.",
};

export default function ResetPasswordPage() {
  return (
    <AuthShell
      eyebrow="Almost done"
      title="Set a new password"
      description="Choose a new password for your account. You'll be able to log in with it right away."
      footer={
        <p>
          Back to{" "}
          <Link href="/login" className="font-medium text-primary hover:text-primary-hover">
            Log in
          </Link>
        </p>
      }
    >
      <Suspense fallback={null}>
        <ResetPasswordForm />
      </Suspense>
    </AuthShell>
  );
}
