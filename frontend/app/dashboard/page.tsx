"use client";

import * as React from "react";
import Link from "next/link";
import {
  Briefcase,
  CheckCircle2,
  Coffee,
  Mic,
  Plane,
  Plus,
  Sparkles,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { AccentStalenessBanner } from "@/components/dashboard/AccentStalenessBanner";
import { DailyChallengeCard } from "@/components/dashboard/DailyChallengeCard";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { ApiError } from "@/lib/api";
import { MASTERY_METRIC_DEFS } from "@/lib/dashboard-data";
import { getProgressDashboard, type ProgressDashboardData } from "@/lib/progressDashboard";
import { getRecentScenarioSessions, type RecentScenarioSession } from "@/lib/scenario";
import { GOAL_DASHBOARD_COPY, normalizeGoal } from "@/lib/goals";

interface CategoryStyle {
  icon: typeof Briefcase;
  badge: string;
  gradient: string;
}

const CATEGORY_STYLES: Record<string, CategoryStyle> = {
  Business: {
    icon: Briefcase,
    badge: "bg-primary text-primary-foreground",
    gradient: "bg-gradient-to-br from-primary to-primary-hover",
  },
  Work: {
    icon: Briefcase,
    badge: "bg-primary text-primary-foreground",
    gradient: "bg-gradient-to-br from-primary to-primary-hover",
  },
  Social: {
    icon: Coffee,
    badge: "bg-accent text-accent-foreground",
    gradient: "bg-gradient-to-br from-accent to-accent/70",
  },
  "Daily Life": {
    icon: Users,
    badge: "bg-accent text-accent-foreground",
    gradient: "bg-gradient-to-br from-accent to-accent/70",
  },
  Travel: {
    icon: Plane,
    badge: "bg-foreground text-background",
    gradient: "bg-gradient-to-br from-foreground to-muted-foreground",
  },
};

// Custom (admin-authored) scenarios can carry any category label, so unknown
// ones fall back to a neutral style rather than being dropped.
const DEFAULT_CATEGORY_STYLE: CategoryStyle = {
  icon: Sparkles,
  badge: "bg-secondary text-secondary-foreground",
  gradient: "bg-gradient-to-br from-muted-foreground to-foreground",
};

function getCategoryStyle(category: string): CategoryStyle {
  return CATEGORY_STYLES[category] ?? DEFAULT_CATEGORY_STYLE;
}

const MASTERY_METRIC_STYLES: Record<
  string,
  { barClassName: string; valueClassName: string }
> = {
  fluency: {
    barClassName: "bg-primary/70 last:bg-primary",
    valueClassName: "text-primary",
  },
  confidence: {
    barClassName: "bg-accent/60 last:bg-accent",
    valueClassName: "text-accent",
  },
  speech: {
    barClassName: "bg-foreground/60 last:bg-foreground",
    valueClassName: "text-foreground",
  },
};

// Which field on the real-time progress payload each mastery card reads —
// "Speech" maps to pronunciation clarity, the closest real signal to what the
// original mock card represented.
const MASTERY_METRIC_SOURCE: Record<string, keyof MetricScores> = {
  fluency: "fluency_score",
  confidence: "confidence_score",
  speech: "pronunciation_score",
};

interface MetricScores {
  confidence_score: number | null;
  fluency_score: number | null;
  vocabulary_score: number | null;
  pronunciation_score: number | null;
}

function scenarioMetaLabel(session: RecentScenarioSession): {
  label: string;
  icon: "users" | "check";
} {
  if (session.status === "completed") {
    return {
      label:
        session.met_goal === true
          ? "Completed · Goal Met"
          : "Completed" +
            (session.confidence_score != null
              ? ` · ${Math.round(session.confidence_score)}% confidence`
              : ""),
      icon: "check",
    };
  }
  if (session.status === "ended_early") {
    return { label: "Ended Early", icon: "users" };
  }
  return { label: "In Progress", icon: "users" };
}

function scenarioHref(session: RecentScenarioSession): string {
  if (session.status === "in_progress") {
    return `/dashboard/scenarios/${session.scenario_key}?resume=${session.session_id}`;
  }
  return `/dashboard/scenarios/${session.scenario_key}`;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const firstName = user?.name?.trim().split(/\s+/)[0] ?? "there";

  // Goal rides along on the AuthContext user, so a profile-page update (which
  // pushes the refreshed user into that context) reorders this dashboard
  // instantly (US-10 AC) without its own network round trip.
  const goal = normalizeGoal(user?.learningGoal);
  const { subtitle, preferredCategory } = GOAL_DASHBOARD_COPY[goal];

  const [dashboard, setDashboard] = React.useState<ProgressDashboardData | null>(null);
  const [dashboardError, setDashboardError] = React.useState<string | null>(null);
  const [recentSessions, setRecentSessions] = React.useState<RecentScenarioSession[] | null>(null);
  const [recentError, setRecentError] = React.useState<string | null>(null);

  React.useEffect(() => {
    getProgressDashboard()
      .then(setDashboard)
      .catch((err) =>
        setDashboardError(err instanceof ApiError ? err.message : "Couldn't load your mastery scores."),
      );

    getRecentScenarioSessions()
      .then((data) => setRecentSessions(data.scenarios))
      .catch((err) =>
        setRecentError(err instanceof ApiError ? err.message : "Couldn't load your recent scenarios."),
      );
  }, []);

  // "Business" preference (from GOAL_DASHBOARD_COPY) is closest to the real
  // catalog's "Work" category — real scenario categories never say "Business".
  const scenarios = React.useMemo(() => {
    if (!recentSessions) return [];
    if (!preferredCategory) return recentSessions;
    const matchesPreferred = (category: string) =>
      preferredCategory === "Business" ? category === "Work" : category === preferredCategory;
    return [...recentSessions].sort((a, b) => {
      const aMatch = matchesPreferred(a.category) ? -1 : 0;
      const bMatch = matchesPreferred(b.category) ? -1 : 0;
      return aMatch - bMatch;
    });
  }, [recentSessions, preferredCategory]);

  const hasNoSessions = dashboard?.is_empty_state || dashboard?.summary_metrics.completed_sessions_count === 0;

  return (
    <div className="flex flex-col gap-8">
      <AccentStalenessBanner />
      <div className="flex animate-fade-up flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <h1 className="font-serif text-h1 font-semibold text-foreground">
            Hi, {firstName}!
          </h1>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">{subtitle}</p>
        </div>
        <Button type="button" size="md">
          <Plus className="h-4 w-4" aria-hidden="true" />
          Start New Session
        </Button>
      </div>

      <DailyChallengeCard />

      <div className="grid grid-cols-1 gap-6">
        <div
          className="animate-fade-up rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm transition-shadow duration-200 hover:shadow-md"
          style={{ animationDelay: "150ms" }}
        >
          <div className="flex items-center justify-between">
            <h2 className="font-serif text-xl font-semibold text-foreground">
              Learning Mastery
            </h2>
            <span className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground">
              This Week
            </span>
          </div>

          {dashboardError ? (
            <p className="mt-6 text-sm text-danger">{dashboardError}</p>
          ) : !dashboard ? (
            <p className="mt-6 text-sm text-muted-foreground">Loading your mastery scores…</p>
          ) : hasNoSessions ? (
            <div className="mt-6 flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border p-8 text-center">
              <p className="text-sm font-medium text-foreground">
                {dashboard.empty_state_prompt ?? "Complete your first session to see your progress!"}
              </p>
              <p className="max-w-sm text-xs text-muted-foreground">
                Your Fluency, Confidence, and Speech scores will show up here once you finish a
                session.
              </p>
            </div>
          ) : (
            <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-3">
              {MASTERY_METRIC_DEFS.map((metric) => {
                const sourceKey = MASTERY_METRIC_SOURCE[metric.id];
                const value =
                  sourceKey === "confidence_score"
                    ? dashboard.summary_metrics.confidence_score.value
                    : dashboard.summary_metrics[sourceKey];
                const bars = dashboard.trend_lines
                  .map((point) => point[sourceKey])
                  .filter((v): v is number => v != null)
                  .slice(-5);

                return (
                  <div key={metric.id} className="flex flex-col gap-3">
                    <div className="flex items-center justify-between text-xs font-medium">
                      <span className="tracking-wide text-muted-foreground">{metric.label}</span>
                      <span
                        className={cn(
                          "font-semibold",
                          MASTERY_METRIC_STYLES[metric.id]?.valueClassName,
                        )}
                      >
                        {value != null ? `${Math.round(value)}%` : "—"}
                      </span>
                    </div>
                    {bars.length > 0 ? (
                      <div className="flex h-16 items-end gap-1.5">
                        {bars.map((height, i) => (
                          <span
                            key={i}
                            className={cn(
                              "flex-1 rounded-sm",
                              MASTERY_METRIC_STYLES[metric.id]?.barClassName,
                            )}
                            style={{ height: `${height}%` }}
                          />
                        ))}
                      </div>
                    ) : (
                      <div className="flex h-16 items-center">
                        <p className="text-xs text-muted-foreground">Not enough data yet</p>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between">
          <h2 className="font-serif text-xl font-semibold text-foreground">
            Recent Scenarios
          </h2>
        </div>

        {recentError ? (
          <p className="mt-4 text-sm text-danger">{recentError}</p>
        ) : !recentSessions ? (
          <p className="mt-4 text-sm text-muted-foreground">Loading your recent scenarios…</p>
        ) : scenarios.length === 0 ? (
          <div className="mt-4 flex min-h-[25vh] flex-col items-center justify-center gap-4 rounded-2xl border border-dashed border-border p-8 text-center">
            <span className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-primary">
              <Sparkles className="h-5 w-5" aria-hidden="true" />
            </span>
            <div className="flex flex-col gap-1">
              <h3 className="font-serif text-lg font-semibold text-foreground">
                No scenarios yet
              </h3>
              <p className="max-w-sm text-xs text-muted-foreground">
                Start a scenario to practice real conversations — it'll show up here once you
                begin.
              </p>
            </div>
            <Button href="/dashboard/explore" size="sm">
              Explore Scenarios
            </Button>
          </div>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
            {scenarios.map((session, index) => {
              const style = getCategoryStyle(session.category);
              const CategoryIcon = style.icon;
              const meta = scenarioMetaLabel(session);
              return (
                <Link
                  key={session.session_id}
                  href={scenarioHref(session)}
                  className="group animate-fade-up overflow-hidden rounded-2xl border border-border bg-surface-elevated shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-md"
                  style={{ animationDelay: `${200 + index * 80}ms` }}
                >
                  <div
                    className={cn(
                      "relative flex h-36 items-center justify-center",
                      style.gradient,
                    )}
                  >
                    <CategoryIcon
                      className="h-10 w-10 text-primary-foreground/90 transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-6"
                      aria-hidden="true"
                    />
                    <span
                      className={cn(
                        "absolute left-3 top-3 rounded-md px-2 py-1 text-[10px] font-semibold uppercase tracking-wide",
                        style.badge,
                      )}
                    >
                      {session.category}
                    </span>
                  </div>
                  <div className="flex flex-col gap-2 p-5">
                    <h3 className="font-serif text-lg font-semibold text-foreground">
                      {session.title}
                    </h3>
                    <p className="text-sm text-muted-foreground">{session.description}</p>
                    <div className="flex items-center gap-1.5 pt-2 text-xs text-muted-foreground">
                      {meta.icon === "check" ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-success" aria-hidden="true" />
                      ) : (
                        <Users className="h-3.5 w-3.5" aria-hidden="true" />
                      )}
                      {meta.label}
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      <button
        type="button"
        aria-label="Start voice session"
        className="fixed bottom-8 right-8 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-md transition-all duration-200 hover:scale-110 hover:bg-primary-hover hover:shadow-lg active:scale-95"
      >
        <Mic className="h-5 w-5" aria-hidden="true" />
      </button>
    </div>
  );
}
