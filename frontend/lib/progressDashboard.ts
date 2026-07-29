import { api } from "./api";

// ── Full time-series dashboard (PDG-US-10/14) ─────────────────────────────────
export interface PrimaryMetric {
  name: string;
  value: number;
  unit: string;
  is_primary: boolean;
  description: string;
}

export interface TrendPoint {
  date: string;
  confidence_score?: number | null;
  fluency_score?: number | null;
  vocabulary_score?: number | null;
  pronunciation_score?: number | null;
  practice_time_minutes: number;
}

export interface ProgressDashboardMetrics {
  confidence_score: PrimaryMetric;
  fluency_score?: number | null;
  vocabulary_score?: number | null;
  pronunciation_score?: number | null;
  total_practice_time_minutes: number;
  total_practice_time_hours: number;
  completed_sessions_count: number;
  vocabulary_growth_count: number;
  daily_streak_days: number;
}

export interface ProgressDashboardData {
  user_id: string;
  generated_at: string;
  sync_status: "synced" | "stale";
  is_stale: boolean;
  is_empty_state: boolean;
  empty_state_prompt?: string | null;
  primary_metric: PrimaryMetric;
  summary_metrics: ProgressDashboardMetrics;
  trend_lines: TrendPoint[];
  flagged_outliers_count: number;
  sync_message?: string | null;
}

export function getProgressDashboard() {
  return api<ProgressDashboardData>("/progress-dashboard/progress");
}

// Retain legacy interface for overview
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

// ── Shared types ──────────────────────────────────────────────────────────────
export interface StreakInfoResponse {
  current_streak: number;
  highest_streak: number;
  freeze_tokens: number;
  last_practice_date: string | null;
  active_freezes: string[];
  last_makeup_drill_month: string | null;
}

export interface PracticeSessionLogResponse {
  session_id: string;
  date: string;
  current_streak: number;
  highest_streak: number;
  freeze_tokens: number;
  token_refunded: boolean;
  tokens_earned: number;
  message: string;
}

export interface ActivateFreezeResponse {
  success: boolean;
  message: string;
  freeze_tokens_remaining: number;
  active_freezes: string[];
}

export interface MakeupDrillResponse {
  success: boolean;
  restored_streak: number;
  message: string;
}

export interface ComponentScoreDetail {
  weight: number;
  recent_average: number | null;
  description: string;
}

export interface ConfidenceBreakdownResponse {
  current_score: number;
  explanation: string;
  components: Record<string, ComponentScoreDetail>;
  session_count: number;
  insufficient_data: boolean;
}

export interface DisputeScoreResponse {
  dispute_id: string;
  session_id: string;
  status: string;
  message: string;
}

export interface BadgeStatus {
  badge_id: string;
  title: string;
  category: string;
  description: string;
  icon: string;
  earned: boolean;
  earned_at: string | null;
  requirement_text: string;
  current_progress: number;
  target_requirement: number;
  progress_label: string;
}

export interface BadgeCatalogResponse {
  total_badges: number;
  earned_count: number;
  badges: BadgeStatus[];
}

export interface MonthlyRollupSummary {
  month: string;
  sessions_count: number;
  avg_confidence_score: number;
  avg_vocabulary_score: number;
  total_practice_seconds: number;
}

export interface ProgressReportResponse {
  start_date: string;
  end_date: string;
  session_count: number;
  confidence_score_trend: Array<{ date: string; score: number }>;
  vocabulary_growth: Array<{ date: string; score: number }>;
  total_practice_time_seconds: number;
  badges_earned: string[];
  is_rollup: boolean;
  monthly_rollups: MonthlyRollupSummary[];
  note: string | null;
}

export interface StreakAppealResponse {
  appeal_id: string;
  status: string;
  message: string;
  restored_streak: number | null;
}

export interface SessionDataPoint {
  session_id: string;
  timestamp: string;
  confidence_score: number;
  fluency_score: number;
  vocabulary_score: number;
  pronunciation_score: number | null;
  duration_seconds: number;
  is_outlier: boolean;
}

export interface AggregatedDataPoint {
  period_label: string;
  start_date: string;
  end_date: string;
  session_count: number;
  avg_confidence: number;
  avg_vocabulary: number;
  total_practice_seconds: number;
  best_outlier_session: SessionDataPoint | null;
  is_gap: boolean;
}

export interface HistoricalDataResponse {
  time_range: string;
  aggregation_level: string;
  raw_sessions: SessionDataPoint[] | null;
  aggregated_points: AggregatedDataPoint[] | null;
}

export interface ExpandDataPointResponse {
  period_label: string;
  sessions: SessionDataPoint[];
}

// ── API calls ─────────────────────────────────────────────────────────────────
export function getStreakInfo(): Promise<StreakInfoResponse> {
  return api<StreakInfoResponse>("/progress-dashboard/streak");
}

export function activateFreeze(date: string): Promise<ActivateFreezeResponse> {
  return api<ActivateFreezeResponse>("/progress-dashboard/streak/freeze", {
    method: "POST",
    body: JSON.stringify({ date }),
  });
}

export function logPracticeSession(data: {
  date?: string;
  duration_seconds?: number;
  fluency_score?: number;
  vocabulary_score?: number;
}): Promise<PracticeSessionLogResponse> {
  return api<PracticeSessionLogResponse>("/progress-dashboard/streak/practice", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function performMakeupDrill(): Promise<MakeupDrillResponse> {
  return api<MakeupDrillResponse>("/progress-dashboard/streak/makeup", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function getConfidenceBreakdown(): Promise<ConfidenceBreakdownResponse> {
  return api<ConfidenceBreakdownResponse>("/progress-dashboard/confidence/breakdown");
}

export function disputeSessionScore(session_id: string, reason: string): Promise<DisputeScoreResponse> {
  return api<DisputeScoreResponse>("/progress-dashboard/confidence/dispute", {
    method: "POST",
    body: JSON.stringify({ session_id, reason }),
  });
}

export function getBadgeCatalog(): Promise<BadgeCatalogResponse> {
  return api<BadgeCatalogResponse>("/progress-dashboard/badges");
}

export function exportProgressReport(start_date: string, end_date: string): Promise<ProgressReportResponse> {
  return api<ProgressReportResponse>("/progress-dashboard/report/export", {
    method: "POST",
    body: JSON.stringify({ start_date, end_date }),
  });
}

export function submitStreakAppeal(data: {
  date_of_break: string;
  reason: string;
  has_evidence: boolean;
  evidence_note?: string;
}): Promise<StreakAppealResponse> {
  return api<StreakAppealResponse>("/progress-dashboard/appeal", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getHistoricalData(time_range: string): Promise<HistoricalDataResponse> {
  return api<HistoricalDataResponse>(`/progress-dashboard/history?time_range=${time_range}`);
}

export function expandPeriodData(period_label: string): Promise<ExpandDataPointResponse> {
  return api<ExpandDataPointResponse>(
    `/progress-dashboard/history/expand?period_label=${encodeURIComponent(period_label)}`
  );
}
