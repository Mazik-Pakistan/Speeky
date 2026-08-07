import { api } from "./api";

/** public_speaking is Q&A-only — the backend refuses a token until the session reaches
 *  qa_phase, because a live agent during the speech would talk over the speaker and its voice
 *  would land in the audio being scored. */
export type LiveCallFeature =
  | "conversation"
  | "interview_coach"
  | "scenario"
  | "coaching"
  | "public_speaking";

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
