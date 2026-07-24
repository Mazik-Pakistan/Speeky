"use client";

import * as React from "react";
import { Award, Trophy } from "lucide-react";
import { ApiError } from "@/lib/api";
import { getTrophyCase, type TrophyCase } from "@/lib/practiceTime";
import { cn } from "@/lib/utils";

function formatHours(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)} min`;
  return `${hours.toFixed(1)}h`;
}

/** PDG-US-15: Progress Dashboard - Practice Time Milestones (Trophy Case). */
export function PracticeTimeMilestones() {
  const [trophyCase, setTrophyCase] = React.useState<TrophyCase | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);

  React.useEffect(() => {
    getTrophyCase()
      .then(setTrophyCase)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong."))
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
        <p className="text-sm text-muted-foreground">Loading your practice milestones…</p>
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

  if (!trophyCase) return null;

  const { lifetime_hours, trophies, next_milestone_hours, progress_to_next } = trophyCase;

  return (
    <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="font-serif text-xl font-semibold text-foreground">Practice Time</h2>
        <span className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
          {formatHours(lifetime_hours)} lifetime
        </span>
      </div>

      {next_milestone_hours !== null ? (
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Next milestone</span>
            <span>{lifetime_hours.toFixed(1)}h / {next_milestone_hours}h</span>
          </div>
          <div className="mt-1.5 h-2 w-full rounded-full bg-muted">
            <div
              className="h-2 rounded-full bg-primary transition-all"
              style={{ width: `${Math.round(progress_to_next * 100)}%` }}
            />
          </div>
        </div>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">
          You've unlocked every milestone. Incredible consistency!
        </p>
      )}

      <div className="mt-6">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Trophy Case
        </p>
        {trophies.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border p-6 text-center">
            <Trophy className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">
              Complete practice sessions to earn your first badge.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {trophies.map((trophy) => (
              <div
                key={trophy.hours}
                className={cn(
                  "flex flex-col items-center gap-2 rounded-xl border border-border bg-surface p-4 text-center",
                )}
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-accent/15 text-accent">
                  <Award className="h-5 w-5" aria-hidden="true" />
                </span>
                <span className="text-sm font-semibold text-foreground">{trophy.hours}h</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
