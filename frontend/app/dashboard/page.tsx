"use client";

import * as React from "react";
import {
  Briefcase,
  CheckCircle2,
  Coffee,
  Flame,
  Mic,
  Plane,
  Plus,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import {
  DAILY_STREAK,
  MASTERY_METRICS,
  RECENT_SCENARIOS,
  type RecentScenario,
} from "@/lib/dashboard-data";
import { GOAL_DASHBOARD_COPY, getLearningGoal, type LearningGoal } from "@/lib/goals";

const CATEGORY_STYLES: Record<
  RecentScenario["category"],
  { icon: typeof Briefcase; badge: string; gradient: string }
> = {
  Business: {
    icon: Briefcase,
    badge: "bg-primary text-primary-foreground",
    gradient: "bg-gradient-to-br from-primary to-primary-hover",
  },
  Social: {
    icon: Coffee,
    badge: "bg-accent text-accent-foreground",
    gradient: "bg-gradient-to-br from-accent to-accent/70",
  },
  Travel: {
    icon: Plane,
    badge: "bg-foreground text-background",
    gradient: "bg-gradient-to-br from-foreground to-muted-foreground",
  },
};

export default function DashboardPage() {
  const { user } = useAuth();
  const firstName = user?.name?.trim().split(/\s+/)[0] ?? "there";

  // Read after mount (localStorage isn't available during SSR) so the
  // dashboard reorders instantly whenever the goal changes (US-10 AC),
  // without needing a network round trip.
  const [goal, setGoal] = React.useState<LearningGoal>("improve_english");
  React.useEffect(() => {
    if (!user) return;
    setGoal(getLearningGoal(user.id));
  }, [user]);

  const { subtitle, preferredCategory } = GOAL_DASHBOARD_COPY[goal];
  const scenarios = preferredCategory
    ? [...RECENT_SCENARIOS].sort((a, b) => {
        const aMatch = a.category === preferredCategory ? -1 : 0;
        const bMatch = b.category === preferredCategory ? -1 : 0;
        return aMatch - bMatch;
      })
    : RECENT_SCENARIOS;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex animate-fade-up flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-foreground">
            Hi, {firstName}!
          </h1>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">{subtitle}</p>
        </div>
        <Button type="button" size="md">
          <Plus className="h-4 w-4" aria-hidden="true" />
          Start New Session
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_2fr]">
        <div
          className="flex animate-fade-up flex-col justify-between gap-6 rounded-2xl bg-gradient-to-br from-accent to-accent/80 p-6 text-accent-foreground shadow-sm transition-transform duration-200 hover:-translate-y-0.5"
          style={{ animationDelay: "75ms" }}
        >
          <div>
            <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-accent-foreground/80">
              <Flame className="h-4 w-4" aria-hidden="true" />
              Daily Streak
            </span>
            <p className="mt-3 flex items-baseline gap-2">
              <span className="text-5xl font-bold tracking-tight">
                {DAILY_STREAK.days}
              </span>
              <span className="text-lg text-accent-foreground/80">Days</span>
            </p>
          </div>
          <div>
            <p className="text-sm text-accent-foreground/90">{DAILY_STREAK.message}</p>
            <div className="mt-4 flex gap-1.5">
              {Array.from({ length: 5 }, (_, i) => (
                <span
                  key={i}
                  className="h-1.5 flex-1 rounded-full bg-accent-foreground/30"
                />
              ))}
            </div>
          </div>
        </div>

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
          <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-3">
            {MASTERY_METRICS.map((metric) => (
              <div key={metric.id} className="flex flex-col gap-3">
                <div className="flex items-center justify-between text-xs font-medium">
                  <span className="tracking-wide text-muted-foreground">
                    {metric.label}
                  </span>
                  <span className={cn("font-semibold", metric.valueClassName)}>
                    {metric.value}%
                  </span>
                </div>
                <div className="flex h-16 items-end gap-1.5">
                  {metric.bars.map((height, i) => (
                    <span
                      key={i}
                      className={cn("flex-1 rounded-sm", metric.barClassName)}
                      style={{ height: `${height}%` }}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between">
          <h2 className="font-serif text-xl font-semibold text-foreground">
            Recent Scenarios
          </h2>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {scenarios.map((scenario, index) => {
            const style = CATEGORY_STYLES[scenario.category];
            const CategoryIcon = style.icon;
            return (
              <div
                key={scenario.id}
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
                    {scenario.category}
                  </span>
                </div>
                <div className="flex flex-col gap-2 p-5">
                  <h3 className="font-serif text-lg font-semibold text-foreground">
                    {scenario.title}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {scenario.description}
                  </p>
                  <div className="flex items-center gap-1.5 pt-2 text-xs text-muted-foreground">
                    {scenario.metaIcon === "check" ? (
                      <CheckCircle2
                        className="h-3.5 w-3.5 text-success"
                        aria-hidden="true"
                      />
                    ) : (
                      <Users className="h-3.5 w-3.5" aria-hidden="true" />
                    )}
                    {scenario.meta}
                  </div>
                  {scenario.progress !== undefined ? (
                    <div className="h-1.5 w-full rounded-full bg-muted">
                      <div
                        className="h-1.5 rounded-full bg-primary"
                        style={{ width: `${scenario.progress}%` }}
                      />
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
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
