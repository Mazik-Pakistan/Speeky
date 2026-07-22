import { api } from "./api";

// ── Types (mirrors Backend/services/progress_dashboard_service.py response shape) ─

export interface VocabularyGrowth {
  new_words_count: number;
  new_words?: string[];
  is_empty_state: boolean;
  is_zero_growth: boolean;
  message: string | null;
}

export interface VocabularyHistoryPoint {
  date: string;
  vocabulary_score: number;
}

export interface ProgressDashboardOverview {
  has_data: boolean;
  generated_at: string;
  metrics: {
    practice_time_minutes: number;
    confidence_score: number | null;
    fluency_score: number | null;
    vocabulary_score: number | null;
  };
  vocabulary_growth: VocabularyGrowth;
  vocabulary_history: VocabularyHistoryPoint[];
}

export function getProgressDashboardOverview() {
  return api<ProgressDashboardOverview>("/progress-dashboard/overview");
}
