"use client";

import * as React from "react";
import { getFeatureAccess, type FeatureAccessSummary } from "@/lib/assessment";
import { useAuth } from "@/contexts/AuthContext";

interface AssessmentContextValue {
  access: FeatureAccessSummary | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
}

const AssessmentContext = React.createContext<AssessmentContextValue | undefined>(
  undefined
);

/**
 * Feature-access gating state (US-12) — scoped to the dashboard, not the
 * whole app, since it's only meaningful once a user is authenticated.
 */
export function AssessmentProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [access, setAccess] = React.useState<FeatureAccessSummary | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);

  const refresh = React.useCallback(async () => {
    if (!user) {
      setAccess(null);
      setIsLoading(false);
      return;
    }
    try {
      setIsLoading(true);
      const summary = await getFeatureAccess();
      setAccess(summary);
    } catch {
      setAccess(null);
    } finally {
      setIsLoading(false);
    }
  }, [user]);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <AssessmentContext.Provider value={{ access, isLoading, refresh }}>
      {children}
    </AssessmentContext.Provider>
  );
}

export function useAssessmentAccess() {
  const ctx = React.useContext(AssessmentContext);
  if (!ctx) {
    throw new Error("useAssessmentAccess must be used within an AssessmentProvider");
  }
  return ctx;
}
