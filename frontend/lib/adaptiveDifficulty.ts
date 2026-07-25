import { api } from "./api";

// ── Shared Interfaces ─────────────────────────────────────────────────────────

export interface ScoredAttemptRequest {
  metric_name: string;
  score: number;
  drill_item: string;
}

export interface ScoredAttemptResponse {
  user_id: string;
  metric_name: string;
  score: number;
  drill_item: string;
  previous_level: number;
  current_level: number;
  escalated: boolean;
  regressed: boolean;
  consecutive_mastery_count: number;
  distinct_drill_items_count: number;
  message: string;
}

export interface GenerateDrillRequest {
  metric_name: string;
  level?: number;
}

export interface GenerateDrillResponse {
  metric_name: string;
  level: number;
  drill_phrase: string;
  source: "llm" | "static_fallback";
  complexity_notes: string;
}

export interface EscalationEvent {
  metric_name: string;
  event_type: "initial" | "escalation" | "regression";
  from_level: number;
  to_level: number;
  reached_at: string;
  trigger_reason: string;
}

export interface EscalationHistoryResponse {
  metric_name: string;
  current_level: number;
  history: EscalationEvent[];
}

export interface MetricProgressionState {
  metric_name: string;
  current_level: number;
  consecutive_mastery_count: number;
  recent_drill_items: string[];
  total_attempts: number;
  last_score: number | null;
  last_attempt_at: string | null;
}

// ── API Calls ─────────────────────────────────────────────────────────────────

export function recordAttempt(data: ScoredAttemptRequest): Promise<ScoredAttemptResponse> {
  return api<ScoredAttemptResponse>("/adaptive-difficulty/attempt", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function generateDrill(data: GenerateDrillRequest): Promise<GenerateDrillResponse> {
  return api<GenerateDrillResponse>("/adaptive-difficulty/generate-drill", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getEscalationHistory(metricName: string): Promise<EscalationHistoryResponse> {
  return api<EscalationHistoryResponse>(
    `/adaptive-difficulty/history/${encodeURIComponent(metricName)}`
  );
}

export function getMetricState(metricName: string): Promise<MetricProgressionState> {
  return api<MetricProgressionState>(
    `/adaptive-difficulty/state/${encodeURIComponent(metricName)}`
  );
}
