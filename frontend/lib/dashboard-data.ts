import {
  Briefcase,
  Coffee,
  Compass,
  Home,
  Plane,
  TrendingUp,
  User,
  UtensilsCrossed,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface DashboardNavLink {
  label: string;
  href: string;
  icon: LucideIcon;
}

export const DASHBOARD_NAV_LINKS: DashboardNavLink[] = [
  { label: "Home", href: "/dashboard", icon: Home },
  { label: "Explore", href: "/dashboard/explore", icon: Compass },
  { label: "Progress", href: "/dashboard/progress", icon: TrendingUp },
  { label: "Profile", href: "/dashboard/profile", icon: User },
];

export const DAILY_STREAK = {
  days: 14,
  message: "You're in the top 5% of learners this month. Keep the momentum going!",
};

export interface MasteryMetric {
  id: string;
  label: string;
  value: number;
  bars: number[];
  barClassName: string;
  valueClassName: string;
}

export const MASTERY_METRICS: MasteryMetric[] = [
  {
    id: "fluency",
    label: "FLUENCY",
    value: 85,
    bars: [35, 50, 65, 85, 100],
    barClassName: "bg-primary/70 last:bg-primary",
    valueClassName: "text-primary",
  },
  {
    id: "confidence",
    label: "CONFIDENCE",
    value: 72,
    bars: [25, 40, 55, 70, 90],
    barClassName: "bg-accent/60 last:bg-accent",
    valueClassName: "text-accent",
  },
  {
    id: "speech",
    label: "SPEECH",
    value: 92,
    bars: [45, 60, 100, 80, 95],
    barClassName: "bg-foreground/60 last:bg-foreground",
    valueClassName: "text-foreground",
  },
];

export interface RecentScenario {
  id: string;
  category: "Business" | "Social" | "Travel";
  title: string;
  description: string;
  meta: string;
  metaIcon: "users" | "check";
  progress?: number;
}

export const RECENT_SCENARIOS: RecentScenario[] = [
  {
    id: "q3-budget-presentation",
    category: "Business",
    title: "Q3 Budget Presentation",
    description:
      "Practice articulating financial projections and handling tough questions.",
    meta: "8 colleagues joined",
    metaIcon: "users",
  },
  {
    id: "ordering-at-a-cafe",
    category: "Social",
    title: "Ordering at a Café",
    description: "Master casual interactions, dietary requests, and small talk.",
    meta: "Completed Mastery",
    metaIcon: "check",
  },
  {
    id: "flight-connection-issues",
    category: "Travel",
    title: "Flight Connection Issues",
    description: "Learn to negotiate and solve travel problems under pressure.",
    meta: "70% Progress",
    metaIcon: "users",
    progress: 70,
  },
];

// ── Explore / "Choose Your Mission" catalog ─────────────────────────────────
// Mirrors UI Designs/choose_your_mission/code.html. Purely presentational —
// there is no scenario-catalog or AI-practice-session backend yet, so
// "Start Practicing" only goes somewhere real for the one scenario wired to
// the Meeting Prep feedback mockup (US-66); the rest are inert previews.

export type ExploreCategory = "Work" | "Social" | "Travel" | "Daily Life";

export interface ExploreScenario {
  id: string;
  category: ExploreCategory;
  icon: LucideIcon;
  title: string;
  description: string;
  difficulty: string;
  featured?: boolean;
  href?: string;
}

export const EXPLORE_CATEGORIES: ExploreCategory[] = [
  "Work",
  "Social",
  "Travel",
  "Daily Life",
];

export const EXPLORE_SCENARIOS: ExploreScenario[] = [
  {
    id: "job-interview-prep",
    category: "Work",
    icon: Briefcase,
    title: "Job Interview Preparation",
    description:
      "Practice answering tough behavioral questions and negotiating your offer.",
    difficulty: "High Difficulty",
    featured: true,
  },
  {
    id: "meeting-new-colleagues",
    category: "Work",
    icon: Users,
    title: "Meeting Preparation",
    description:
      "Navigate small talk, agenda framing, and professional introductions.",
    difficulty: "Intermediate",
    href: "/dashboard/explore/meeting-prep",
  },
  {
    id: "ordering-coffee",
    category: "Social",
    icon: Coffee,
    title: "Ordering Coffee",
    description: "Master quick interactions and custom orders at a busy cafe.",
    difficulty: "Beginner",
  },
  {
    id: "airport-check-in",
    category: "Travel",
    icon: Plane,
    title: "Airport Check-in",
    description: "Practice logistics, handling delays, and gate changes.",
    difficulty: "Essential",
  },
  {
    id: "dinner-with-friends",
    category: "Daily Life",
    icon: UtensilsCrossed,
    title: "Dinner with Friends",
    description: "Practice casual storytelling and natural conversational flow.",
    difficulty: "Intermediate",
  },
];
