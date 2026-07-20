import { api } from "./api";

export type InterruptionType = "phone_call" | "app_backgrounded" | "connectivity_drop" | "manual";
export type InterruptionStatus = "active" | "resumed" | "stale";

export interface InterruptionResult {
  interruption_id: string;
  session_id: string;
  status: InterruptionStatus;
  interruption_count_this_session: number;
  logged_at: string;
}

export interface InterruptionStatusResult {
  session_id: string;
  has_active_interruption: boolean;
  interruption_count_this_session: number;
  last_interruption_at: string | null;
}

export interface ResumeResult {
  session_id: string;
  status: InterruptionStatus;
  partial_answer_text: string | null;
  stale: boolean;
  message: string;
}

export interface MemoryProfile {
  user_id: string;
  sessions_recorded: number;
  recurring_weaknesses: string[];
  recurring_strengths: string[];
  recent_topics: string[];
  last_updated: string;
}

export interface PersonalizedOpening {
  user_id: string;
  has_history: boolean;
  opening_message: string;
}

export function logInterruption(data: {
  session_id: string;
  session_type: string;
  interruption_type: InterruptionType;
  partial_answer_text?: string;
}) {
  return api<InterruptionResult>("/session-memory/interruptions", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getInterruptionStatus(sessionId: string) {
  return api<InterruptionStatusResult>(`/session-memory/interruptions/${sessionId}/status`);
}

export function resumeInterruptedSession(sessionId: string) {
  return api<ResumeResult>("/session-memory/resume", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export function recordSessionMemory(data: {
  session_id: string;
  session_type: string;
  flags_seen?: string[];
  topic_or_mode?: string;
  overall_score?: number;
}) {
  return api<MemoryProfile>("/session-memory/profile/record-session", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function getMemoryProfile() {
  return api<MemoryProfile>("/session-memory/profile");
}

export function getPersonalizedOpening() {
  return api<PersonalizedOpening>("/session-memory/profile/personalized-opening");
}
