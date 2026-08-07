import { api } from "./api";

export type LiveCallFeature = "conversation" | "interview_coach" | "scenario" | "coaching";

export interface LiveCallTokenResult {
  token: string;
  url: string;
  room_name: string;
}

export function fetchLiveCallToken(feature: LiveCallFeature, sessionId: string) {
  return api<LiveCallTokenResult>("/live-call/token", {
    method: "POST",
    body: JSON.stringify({ feature, session_id: sessionId }),
  });
}
