import { api } from "./api";

// ── Types (mirrors Backend/services/practice_time_service.py response shapes) ─

export interface Milestone {
  hours: number;
  message: string;
}

export interface PracticeTimePingResult {
  credited_seconds: number;
  is_primary_session: boolean;
  lifetime_hours: number | null;
  newly_unlocked: Milestone[];
}

export interface TrophyCase {
  lifetime_hours: number;
  unlocked_milestone_hours: number[];
  trophies: Milestone[];
  next_milestone_hours: number | null;
  progress_to_next: number;
}

export function pingPracticeTime(sessionType: "scenario", sessionId: string) {
  return api<PracticeTimePingResult>("/practice-time/ping", {
    method: "POST",
    body: JSON.stringify({ session_type: sessionType, session_id: sessionId }),
  });
}

export function getTrophyCase() {
  return api<TrophyCase>("/practice-time/trophies");
}
