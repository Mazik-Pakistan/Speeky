"use client";

import * as React from "react";
import { Coffee, X } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { dismissOveruseNudge, sendOveruseHeartbeat, type OveruseNudgePayload } from "@/lib/overuse";

const HEARTBEAT_INTERVAL_MS = 60_000;

/**
 * Healthy Engagement Safeguard (US-170 / GAP-09) — non-blocking, dismissible break
 * suggestion. Sends a heartbeat every minute while the dashboard shell is mounted, as
 * a proxy for "continuous active use" — this stays outside Chat/Pronunciation Coach's
 * own code (neither is touched here) and only consumes the heartbeat signal those
 * modules would ideally emit directly in a fuller integration.
 */
export function OveruseNudgeBanner() {
  const { user } = useAuth();
  const [nudge, setNudge] = React.useState<OveruseNudgePayload | null>(null);
  const [dismissing, setDismissing] = React.useState(false);

  React.useEffect(() => {
    if (!user) return;

    let cancelled = false;
    async function beat() {
      try {
        const res = await sendOveruseHeartbeat();
        if (!cancelled && res.nudge) setNudge(res.nudge);
      } catch {
        // Non-critical background signal — fail silently, never interrupt practice.
      }
    }

    beat();
    const id = window.setInterval(beat, HEARTBEAT_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [user]);

  if (!nudge) return null;

  async function handleDismiss() {
    setDismissing(true);
    try {
      await dismissOveruseNudge();
    } finally {
      setNudge(null);
      setDismissing(false);
    }
  }

  return (
    <div className="mb-6 flex flex-col items-start gap-3 rounded-xl border border-border bg-secondary/60 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-2.5">
        <Coffee className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
        <p className="text-foreground">{nudge.message}</p>
      </div>
      <button
        type="button"
        onClick={handleDismiss}
        disabled={dismissing}
        aria-label="Dismiss"
        className="shrink-0 rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-surface hover:text-foreground disabled:opacity-50"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
