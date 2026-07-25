import { api } from "./api";

export interface WordClassification {
  word: string;
  correct: boolean;
}

export interface PronunciationSession {
  session_id: string;
  status: "active" | "interrupted" | "completed";
  phoneme: string;
  phoneme_tag: string;
  sentence: string;
  message?: string | null;
  started_at?: string;
}

export interface AttemptResult {
  session_id: string;
  message_key: string;
  message: string;
  words: WordClassification[];
  transcript?: string;
  next_sentence?: string | null;
  next_phoneme?: string | null;
  next_phoneme_tag?: string | null;
}

export interface RetryResult {
  session_id: string;
  message: string;
  frustration_breakdown: boolean;
  transcript?: string;
}

export interface ResumeCheck {
  found: boolean;
  session_id?: string | null;
  message: string;
  stale: boolean;
}

export interface ResumeResult {
  session_id: string;
  status: "active" | "interrupted" | "completed";
  phoneme: string;
  phoneme_tag: string;
  sentence: string;
  message: string;
}

export interface PhonemeAccuracy {
  phoneme: string;
  attempts: number;
  correct_words: number;
  total_words: number;
}

export interface SessionSummary {
  session_id: string;
  status: string;
  attempt_count: number;
  phoneme_accuracy: PhonemeAccuracy[];
  ended_at: string;
}

function getDeviceId(): string {
  if (typeof window === "undefined") return "server";
  const key = "speeky:pronunciation-device-id";
  let id = window.localStorage.getItem(key);
  if (!id) {
    id = `web_${Math.random().toString(36).slice(2)}_${Date.now()}`;
    window.localStorage.setItem(key, id);
  }
  return id;
}

export function startPronunciationSession() {
  return api<PronunciationSession>("/pronunciation-coach/start", {
    method: "POST",
    body: JSON.stringify({ device_id: getDeviceId() }),
  });
}

export function submitAttempt(sessionId: string, audio: Blob) {
  const form = new FormData();
  form.append("audio", audio, "attempt.webm");
  return api<AttemptResult>(`/pronunciation-coach/${sessionId}/attempt`, {
    method: "POST",
    body: form,
  });
}

export function retryWord(sessionId: string, targetWord: string, audio: Blob) {
  const form = new FormData();
  form.append("target_word", targetWord);
  form.append("audio", audio, "retry.webm");
  return api<RetryResult>(`/pronunciation-coach/${sessionId}/retry`, {
    method: "POST",
    body: form,
  });
}

export function interruptSession(sessionId: string) {
  return api<{ session_id: string; status: string; message: string }>(
    `/pronunciation-coach/${sessionId}/interrupt`,
    { method: "POST" }
  );
}

export function checkResumableSession() {
  return api<ResumeCheck>("/pronunciation-coach/resume");
}

export function resumeSession(sessionId: string) {
  return api<ResumeResult>(`/pronunciation-coach/${sessionId}/resume`, {
    method: "POST",
    body: JSON.stringify({ device_id: getDeviceId() }),
  });
}

export function endSession(sessionId: string) {
  return api<SessionSummary>(`/pronunciation-coach/${sessionId}/end`, { method: "POST" });
}
