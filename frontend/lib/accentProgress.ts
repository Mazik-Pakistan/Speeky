import { api } from "./api";

// ── Types (mirrors Backend/services/accent_progress_service.py response shapes) ─

export type AccentTrend = "improved" | "stagnated" | "degraded";

export interface AccentMetricRow {
  key: string;
  label: string;
  month1_score: number;
  month3_score: number | null;
  trend: AccentTrend | null;
  tune_up_prompt: string | null;
}

export interface AccentProgressMatrix {
  has_baseline: boolean;
  force_baseline: boolean;
  message?: string;
  locked?: boolean;
  days_until_unlock?: number | null;
  baseline_completed_at?: string;
  current_completed_at?: string | null;
  metrics?: AccentMetricRow[];
}

export interface SubmitAccentAssessmentInput {
  pronunciation_score: number;
  word_stress_score: number;
  intonation_score: number;
  clarity_score: number;
}

export interface SubmitAccentAssessmentResult {
  assessment_id: string;
  month_index: number;
  completed_at: string;
  is_baseline: boolean;
}

export function getAccentProgressMatrix() {
  return api<AccentProgressMatrix>("/accent-progress/matrix");
}

export function submitAccentAssessment(data: SubmitAccentAssessmentInput) {
  return api<SubmitAccentAssessmentResult>("/accent-progress/assessments", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
