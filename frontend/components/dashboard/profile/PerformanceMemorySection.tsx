"use client";

import * as React from "react";
import { TrendingUp } from "lucide-react";
import { getMemoryProfile, type MemoryProfile } from "@/lib/sessionMemory";

/** US-28: cross-session performance memory (Interview Coach, Workplace Coach, etc). */
export function PerformanceMemorySection() {
  const [profile, setProfile] = React.useState<MemoryProfile | null>(null);

  React.useEffect(() => {
    getMemoryProfile()
      .then(setProfile)
      .catch(() => {});
  }, []);

  if (!profile || profile.sessions_recorded === 0) return null;

  return (
    <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-primary">
          <TrendingUp className="h-4 w-4" aria-hidden="true" />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-foreground">Performance Memory</h2>
          <p className="text-sm text-muted-foreground">
            Patterns Speeky has noticed across your {profile.sessions_recorded} recent sessions.
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Recurring strengths
          </p>
          <p className="mt-1 text-sm text-foreground">
            {profile.recurring_strengths.join(", ") || "Still building a track record"}
          </p>
        </div>
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Areas to watch
          </p>
          <p className="mt-1 text-sm text-foreground">
            {profile.recurring_weaknesses.join(", ") || "No recurring issues"}
          </p>
        </div>
      </div>
    </div>
  );
}
