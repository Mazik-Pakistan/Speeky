"use client";

import * as React from "react";
import { toast } from "react-toastify";
import { TrendingUp } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { ApiError } from "@/lib/api";
import { getMemoryProfile, setSessionMemoryOptOut, type MemoryProfile } from "@/lib/sessionMemory";

/** US-28: cross-session performance memory (Scenarios, Interview Coach, Workplace Coach,
 *  etc) — separate system/toggle from ConversationMemorySection's remembered facts, which
 *  is AI Conversation only. This one drives the "welcome back" greeting on those pages. */
export function PerformanceMemorySection() {
  const [profile, setProfile] = React.useState<MemoryProfile | null>(null);

  React.useEffect(() => {
    getMemoryProfile()
      .then(setProfile)
      .catch(() => {});
  }, []);

  async function handleOptOut(enabled: boolean) {
    try {
      const result = await setSessionMemoryOptOut(enabled);
      setProfile((prev) => (prev ? { ...prev, opted_out: result.opted_out, sessions_recorded: result.opted_out ? 0 : prev.sessions_recorded } : prev));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Something went wrong.");
    }
  }

  if (!profile) return null;

  return (
    <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-primary">
            <TrendingUp className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-foreground">Performance Memory</h2>
            <p className="text-sm text-muted-foreground">
              {profile.sessions_recorded > 0
                ? `Patterns Speeky has noticed across your ${profile.sessions_recorded} recent sessions.`
                : "Carries context from your Scenario and Interview Coach sessions into the next one's greeting."}
            </p>
          </div>
        </div>
        <Switch
          checked={!profile.opted_out}
          onCheckedChange={(checked) => handleOptOut(!checked)}
          label="Remember context across scenario & interview sessions"
          hideLabel
        />
      </div>

      {profile.sessions_recorded > 0 ? (
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
      ) : null}
    </div>
  );
}
