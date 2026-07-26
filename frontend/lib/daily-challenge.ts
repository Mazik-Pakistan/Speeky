import { api } from "./api";
import type { OveruseNudgePayload } from "./overuse";

/** Anti-gaming detection for Daily Challenge completion (US-168). */

export type ChallengeStatus =
  | "qualified"
  | "qualified_retroactive"
  | "incomplete_low_engagement"
  | "incomplete_duration"
  | "rejected_non_interactive";

export interface StartChallengeResponse {
  session_id: string;
  user_id: string;
  started_at: string;
}

export interface CompleteChallengeResponse {
  session_id: string;
  status: ChallengeStatus;
  current_streak: number;
  longest_streak: number;
  quality_score: number;
  pattern: string | null;
  message: string | null;
  milestone_days: number | null;
  milestone_message: string | null;
  overuse_nudge: OveruseNudgePayload | null;
}

export interface DisputeSessionResponse {
  session_id: string;
  dispute_status: "none" | "pending" | "resolved_genuine" | "resolved_denied";
  message: string;
}

export interface StreakResponse {
  user_id: string;
  current_streak: number;
  longest_streak: number;
  qualified_dates: string[];
}

export function startDailyChallenge() {
  return api<StartChallengeResponse>("/daily-challenge/start", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function addChallengeTurn(sessionId: string, audio: Blob) {
  const form = new FormData();
  form.append("session_id", sessionId);
  form.append("audio", audio, "turn.webm");
  return api<{ session_id: string; turn_count: number }>("/daily-challenge/turn", {
    method: "POST",
    body: form,
  });
}

export function completeDailyChallenge(sessionId: string) {
  return api<CompleteChallengeResponse>("/daily-challenge/complete", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export function disputeChallengeSession(sessionId: string) {
  return api<DisputeSessionResponse>("/daily-challenge/dispute", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export function getDailyChallengeStreak() {
  return api<StreakResponse>("/daily-challenge/streak");
}
