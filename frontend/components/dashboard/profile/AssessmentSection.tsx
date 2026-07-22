"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  dismissReassessmentPrompt,
  getReassessmentEligibility,
  startReassessment,
  type ReassessmentEligibility,
} from "@/lib/assessment";
import { useAssessmentAccess } from "@/contexts/AssessmentContext";

const STATUS_LABELS: Record<string, string> = {
  UNASSESSED: "Not yet assessed",
  IN_PROGRESS: "Assessment in progress",
  COMPLETED: "Baseline complete",
  PLATEAUED: "Baseline complete — plateaued",
};

/** US-14: On-Demand Re-Assessment Request. */
export function AssessmentSection() {
  const router = useRouter();
  const { access, isLoading: accessLoading, refresh } = useAssessmentAccess();
  const [eligibility, setEligibility] = React.useState<ReassessmentEligibility | null>(null);
  const [isLoadingEligibility, setIsLoadingEligibility] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [earlyRetakeError, setEarlyRetakeError] = React.useState<string | null>(null);
  const [isRequesting, setIsRequesting] = React.useState(false);

  const isAssessed =
    access?.assessment_status === "COMPLETED" || access?.assessment_status === "PLATEAUED";

  React.useEffect(() => {
    if (!isAssessed) {
      setIsLoadingEligibility(false);
      return;
    }
    getReassessmentEligibility()
      .then(setEligibility)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong."))
      .finally(() => setIsLoadingEligibility(false));
  }, [isAssessed]);

  async function handleRetake(isEarly: boolean) {
    setError(null);
    setEarlyRetakeError(null);
    setIsRequesting(true);
    try {
      await startReassessment(isEarly);
      // AssessmentProvider persists across routes within /dashboard, so its
      // last-fetched `access` (still "COMPLETED") would otherwise be stale
      // the instant /dashboard/assessment mounts — refresh it before
      // navigating so that page doesn't show "already completed" over the
      // reassessment it just started.
      await refresh();
      router.push("/dashboard/assessment");
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong.";
      if (isEarly) setEarlyRetakeError(message);
      else setError(message);
    } finally {
      setIsRequesting(false);
    }
  }

  async function handleDismiss() {
    try {
      await dismissReassessmentPrompt();
      setEligibility((prev) => (prev ? { ...prev, should_show_prompt: false } : prev));
    } catch {
      // Non-critical — the prompt just won't clear from this view.
    }
  }

  return (
    <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-primary">
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-foreground">Baseline Assessment</h2>
          <p className="text-sm text-muted-foreground">
            {accessLoading
              ? "Loading status..."
              : STATUS_LABELS[access?.assessment_status ?? ""] ?? "Unknown status"}
          </p>
        </div>
      </div>

      {!isAssessed && !accessLoading ? (
        <div className="mt-4">
          <p className="text-sm text-muted-foreground">
            Complete your baseline assessment to unlock personalized coaching
            and enable re-assessment tracking.
          </p>
          <Button href="/dashboard/assessment" size="sm" className="mt-3">
            Take Assessment
          </Button>
        </div>
      ) : null}

      {isAssessed && isLoadingEligibility ? (
        <p className="mt-4 text-sm text-muted-foreground">Checking eligibility...</p>
      ) : null}

      {isAssessed && eligibility ? (
        <div className="mt-4 flex flex-col gap-3">
          <p className="text-sm text-muted-foreground">
            {eligibility.eligibility.is_eligible
              ? "You're eligible for your scheduled re-assessment."
              : eligibility.eligibility.reason}
          </p>

          {eligibility.should_show_prompt && eligibility.prompt ? (
            <div className="flex flex-col gap-2 rounded-xl bg-secondary px-4 py-3 text-sm text-secondary-foreground sm:flex-row sm:items-center sm:justify-between">
              <span>{eligibility.prompt.message}</span>
              <button
                type="button"
                onClick={handleDismiss}
                className="shrink-0 text-xs font-medium underline-offset-2 hover:underline"
              >
                Remind me later
              </button>
            </div>
          ) : null}

          {error ? <p className="text-sm text-danger">{error}</p> : null}

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              size="sm"
              loading={isRequesting}
              disabled={!eligibility.eligibility.is_eligible}
              onClick={() => handleRetake(false)}
            >
              Retake Assessment
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              loading={isRequesting}
              onClick={() => handleRetake(true)}
            >
              Request Early Retake
            </Button>
          </div>
          {earlyRetakeError ? (
            <p className="text-xs text-muted-foreground">{earlyRetakeError}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
