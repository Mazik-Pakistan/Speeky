import type { LucideIcon } from "lucide-react";

export interface NavLink {
  label: string;
  href: string;
}

export interface FeatureItem {
  id: string;
  icon: LucideIcon;
  title: string;
  description: string;
}

export interface ComparisonPoint {
  id: string;
  traditional: string;
  speeky: string;
}

export interface StepItem {
  id: string;
  index: number;
  title: string;
  description: string;
}

export interface StatCard {
  id: string;
  icon: LucideIcon;
  label: string;
  value: string;
  delta?: string;
  trend?: "up" | "down" | "neutral";
}

export interface Testimonial {
  id: string;
  name: string;
  role: string;
  quote: string;
  initials: string;
}

export interface FaqItem {
  id: string;
  question: string;
  answer: string;
}

export interface TrustIndicator {
  id: string;
  label: string;
}
