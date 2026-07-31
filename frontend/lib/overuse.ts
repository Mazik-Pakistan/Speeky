import { api } from "./api";

/** Healthy Engagement Safeguard / overuse nudge (US-170). */

export interface OveruseNudgePayload {
  type: string;
  message: string;
  is_followup: boolean;
}

export interface HeartbeatResponse {
  continuous_minutes: number;
  nudge: OveruseNudgePayload | null;
}

export function sendOveruseHeartbeat() {
  return api<HeartbeatResponse>("/overuse/heartbeat", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function dismissOveruseNudge() {
  return api<{ dismissed: boolean; dismissed_at: string }>("/overuse/dismiss", {
    method: "POST",
  });
}
