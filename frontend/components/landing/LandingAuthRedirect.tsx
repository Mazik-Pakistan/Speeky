"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Logged-in users should never land on the marketing page — bounce them to
 * the dashboard. Rendered as a client island inside the (server-rendered)
 * landing page rather than converting the whole page to a client component,
 * so anonymous visitors still get the static HTML immediately; only a
 * logged-in visitor pays the one auth-check round trip before redirecting.
 */
export function LandingAuthRedirect() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  React.useEffect(() => {
    if (!isLoading && user) {
      router.replace("/dashboard");
    }
  }, [isLoading, user, router]);

  return null;
}
