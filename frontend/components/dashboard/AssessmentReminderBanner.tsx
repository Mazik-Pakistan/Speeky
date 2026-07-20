"use client";

import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { useAssessmentAccess } from "@/contexts/AssessmentContext";

/**
 * Persistent, non-blocking reminder for "Unassessed" users (US-12 happy
 * path step 5). The backend already rate-limits how often this should
 * resurface (see gating_service.should_show_assessment_prompt), so this
 * component just reflects `show_assessment_prompt` as-is.
 */
export function AssessmentReminderBanner() {
  const { access } = useAssessmentAccess();

  if (!access?.show_assessment_prompt) {
    return null;
  }

  return (
    <div className="mb-6 flex flex-col items-start gap-3 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-2.5">
        <AlertTriangle
          className="mt-0.5 h-4 w-4 shrink-0 text-warning"
          aria-hidden="true"
        />
        <p className="text-foreground">{access.assessment_prompt_message}</p>
      </div>
      <Link
        href="/dashboard/assessment"
        className="shrink-0 rounded-lg bg-warning px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-colors hover:opacity-90"
      >
        Take Assessment
      </Link>
    </div>
  );
}
