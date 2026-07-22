"use client";

import * as React from "react";
import { AlertTriangle, Lock, Mic, Minus, TrendingDown, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  getAccentProgressMatrix,
  type AccentProgressMatrix,
  type AccentTrend,
} from "@/lib/accentProgress";
import { cn } from "@/lib/utils";
import { AccentCheckInModal } from "./AccentCheckInModal";

const TREND_STYLES: Record<AccentTrend, { rowClass: string; icon: typeof TrendingUp; iconClass: string }> = {
  improved: { rowClass: "bg-success/10", icon: TrendingUp, iconClass: "text-success" },
  stagnated: { rowClass: "bg-muted/40", icon: Minus, iconClass: "text-muted-foreground" },
  degraded: { rowClass: "bg-danger/10", icon: TrendingDown, iconClass: "text-danger" },
};

/** ACC-US-15: Accent Progress Tracker - Month-Over-Month Matrix Visualization. */
export function AccentProgressTracker() {
  const [matrix, setMatrix] = React.useState<AccentProgressMatrix | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isCheckInOpen, setIsCheckInOpen] = React.useState(false);

  const loadMatrix = React.useCallback(() => {
    setIsLoading(true);
    getAccentProgressMatrix()
      .then(setMatrix)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong."))
      .finally(() => setIsLoading(false));
  }, []);

  React.useEffect(() => {
    loadMatrix();
  }, [loadMatrix]);

  function handleCheckInSuccess() {
    setIsCheckInOpen(false);
    loadMatrix();
  }

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
        <p className="text-sm text-muted-foreground">Loading your accent progress…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
        <p className="text-sm text-danger">{error}</p>
      </div>
    );
  }

  if (!matrix) return null;

  // E-03: no completed baseline yet — force it before rendering any historical matrix.
  if (matrix.force_baseline) {
    return (
      <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
        <h2 className="font-serif text-xl font-semibold text-foreground">Accent Progress Tracker</h2>
        <div className="mt-6 flex flex-col items-center gap-3 rounded-xl border border-dashed border-border p-8 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-primary">
            <Mic className="h-5 w-5" aria-hidden="true" />
          </span>
          <p className="max-w-sm text-sm text-muted-foreground">{matrix.message}</p>
          <Button type="button" size="sm" onClick={() => setIsCheckInOpen(true)}>
            Complete Baseline Accent Assessment
          </Button>
        </div>
        <AccentCheckInModal
          open={isCheckInOpen}
          onClose={() => setIsCheckInOpen(false)}
          onSuccess={handleCheckInSuccess}
        />
      </div>
    );
  }

  const metrics = matrix.metrics ?? [];

  return (
    <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="font-serif text-xl font-semibold text-foreground">Accent Progress Tracker</h2>
        {!matrix.locked ? (
          <Button type="button" size="sm" variant="outline" onClick={() => setIsCheckInOpen(true)}>
            Log New Check-In
          </Button>
        ) : null}
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        Month 1 baseline vs. your current progress across the four accent metrics.
      </p>

      {/* E-04: horizontal scroll with a fixed left (Metric) column on narrow viewports. */}
      <div className="mt-6 overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[420px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-surface text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <th className="sticky left-0 z-10 bg-surface px-4 py-3">Metric</th>
              <th className="px-4 py-3">Month 1 (Baseline)</th>
              <th className="px-4 py-3">Month 3 (Current)</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((row) => {
              const trendStyle = row.trend ? TREND_STYLES[row.trend] : null;
              const TrendIcon = trendStyle?.icon;
              return (
                <tr
                  key={row.key}
                  className={cn("border-b border-border last:border-b-0", trendStyle?.rowClass)}
                >
                  <td className="sticky left-0 z-10 bg-surface-elevated px-4 py-3 font-medium text-foreground">
                    {row.label}
                  </td>
                  <td className="px-4 py-3 text-foreground">{row.month1_score}%</td>
                  <td className="px-4 py-3">
                    {matrix.locked ? (
                      <span className="flex items-center gap-1.5 text-muted-foreground">
                        <Lock className="h-3.5 w-3.5" aria-hidden="true" />
                        Data unlocking in {matrix.days_until_unlock} days
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 text-foreground">
                        {row.month3_score}%
                        {TrendIcon ? (
                          <TrendIcon className={cn("h-3.5 w-3.5", trendStyle?.iconClass)} aria-hidden="true" />
                        ) : null}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {!matrix.locked
        ? metrics
            .filter((row) => row.trend === "degraded" && row.tune_up_prompt)
            .map((row) => (
              <div
                key={row.key}
                className="mt-4 flex items-start gap-2.5 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
                {row.tune_up_prompt}
              </div>
            ))
        : null}

      <AccentCheckInModal
        open={isCheckInOpen}
        onClose={() => setIsCheckInOpen(false)}
        onSuccess={handleCheckInSuccess}
      />
    </div>
  );
}
