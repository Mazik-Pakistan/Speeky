"use client";

import * as React from "react";
import { BookOpen, ChevronRight, Clock, Gauge, Sparkles, TrendingUp } from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  getProgressDashboardOverview,
  type ProgressDashboardOverview,
} from "@/lib/progressDashboard";
import { cn } from "@/lib/utils";
import { VocabularyDrillDownModal } from "./VocabularyDrillDownModal";

function formatPracticeTime(minutes: number): string {
  if (minutes < 1) return "< 1 min";
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (hours === 0) return `${mins} min`;
  return `${hours}h ${mins}m`;
}

function formatScore(score: number | null): string {
  return score === null ? "—" : `${Math.round(score)}/100`;
}

interface MetricTile {
  id: string;
  label: string;
  value: string;
  icon: typeof Clock;
}

/** PDG-US-14: Progress Dashboard - Vocabulary Growth Tracker. */
export function VocabularyGrowthTracker() {
  const [overview, setOverview] = React.useState<ProgressDashboardOverview | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isDrillDownOpen, setIsDrillDownOpen] = React.useState(false);

  React.useEffect(() => {
    getProgressDashboardOverview()
      .then(setOverview)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong."))
      .finally(() => setIsLoading(false));
  }, []);

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
        <p className="text-sm text-muted-foreground">Loading your progress…</p>
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

  if (!overview) return null;

  const { metrics, vocabulary_growth: growth, vocabulary_history: history } = overview;

  const tiles: MetricTile[] = [
    { id: "time", label: "Practice Time", value: formatPracticeTime(metrics.practice_time_minutes), icon: Clock },
    { id: "confidence", label: "Confidence", value: formatScore(metrics.confidence_score), icon: Gauge },
    { id: "fluency", label: "Fluency", value: formatScore(metrics.fluency_score), icon: TrendingUp },
    { id: "vocabulary", label: "Vocabulary", value: formatScore(metrics.vocabulary_score), icon: BookOpen },
  ];

  return (
    <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="font-serif text-xl font-semibold text-foreground">
          Vocabulary Growth
        </h2>
        <span className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
          All Time
        </span>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {tiles.map((tile) => {
          const isVocabularyTile = tile.id === "vocabulary";
          return (
            <div
              key={tile.id}
              onClick={isVocabularyTile ? () => setIsDrillDownOpen(true) : undefined}
              role={isVocabularyTile ? "button" : undefined}
              tabIndex={isVocabularyTile ? 0 : undefined}
              onKeyDown={
                isVocabularyTile
                  ? (event) => {
                      if (event.key === "Enter" || event.key === " ") setIsDrillDownOpen(true);
                    }
                  : undefined
              }
              className={cn(
                "flex flex-col gap-2 rounded-xl border border-border bg-surface p-4",
                isVocabularyTile &&
                  "cursor-pointer transition-colors hover:border-primary/40 hover:bg-secondary",
              )}
            >
              <span className="flex items-center justify-between gap-1.5 text-xs font-medium text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <tile.icon className="h-3.5 w-3.5" aria-hidden="true" />
                  {tile.label}
                </span>
                {isVocabularyTile ? <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" /> : null}
              </span>
              <span className="font-serif text-2xl font-semibold text-foreground">
                {tile.value}
              </span>
            </div>
          );
        })}
      </div>

      {!overview.has_data ? (
        <div className="mt-6 flex flex-col items-center gap-2 rounded-xl border border-dashed border-border p-8 text-center">
          <Sparkles className="h-6 w-6 text-primary" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">
            Your vocabulary journey starts here. {growth.message}
          </p>
          <a
            href="/dashboard/explore"
            className="mt-2 text-sm font-medium text-primary hover:underline"
          >
            Start a Scenario
          </a>
        </div>
      ) : (
        <div className="mt-6 flex flex-col gap-4">
          <div
            className={cn(
              "flex flex-col gap-2 rounded-xl px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between",
              growth.is_zero_growth ? "bg-secondary text-secondary-foreground" : "bg-success/10 text-foreground",
            )}
          >
            <span className="font-medium">
              {growth.is_zero_growth
                ? growth.message
                : `+${growth.new_words_count} new ${growth.new_words_count === 1 ? "word" : "words"} last session`}
            </span>
            {!growth.is_zero_growth && growth.new_words && growth.new_words.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {growth.new_words.map((word) => (
                  <span
                    key={word}
                    className="rounded-full bg-success/15 px-2.5 py-0.5 text-xs font-medium text-success"
                  >
                    {word}
                  </span>
                ))}
              </div>
            ) : null}
          </div>

          {history.length > 1 ? (
            <div>
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Vocabulary Score Trend
              </p>
              <div className="flex h-20 items-end gap-1.5">
                {history.map((point) => (
                  <span
                    key={point.date}
                    title={`${new Date(point.date).toLocaleDateString()}: ${point.vocabulary_score}`}
                    className="flex-1 rounded-sm bg-primary/70 last:bg-primary"
                    style={{ height: `${Math.max(4, point.vocabulary_score)}%` }}
                  />
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}

      <VocabularyDrillDownModal open={isDrillDownOpen} onClose={() => setIsDrillDownOpen(false)} />
    </div>
  );
}
