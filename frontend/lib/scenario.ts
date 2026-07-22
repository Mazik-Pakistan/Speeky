import { api } from "./api";

export interface ScenarioListItem {
  key: string;
  label: string;
  category: string;
  persona: string;
  intent: string;
  goal_type: "roleplay" | "negotiation";
  target_vocab: string[];
}

export interface ScenarioDetail extends ScenarioListItem {}

export interface StartScenarioResult {
  session_id: string;
  scenario_key: string;
  label: string;
  persona: string;
  intent: string;
  target_vocab: string[];
  opening_message: string;
}

export interface ScenarioTurnResult {
  session_id: string;
  reply: string;
  status: "in_progress" | "completed" | "ended_early";
  classification: "ok" | "silence" | "rambling" | "aggressive" | "emergency";
}

export interface ScenarioEndResult {
  session_id: string;
  status: string;
  scores: {
    politeness: number | null;
    vocabulary: number | null;
    confidence: number | null;
  };
  vocab_used: string[];
  vocab_missing: string[];
  met_goal: boolean | null;
  summary: string;
  suggestion: string;
  graded_by: string;
}

export function getScenarios() {
  return api<{ scenarios: ScenarioListItem[] }>("/scenarios/");
}

export function getScenarioDetail(key: string) {
  return api<ScenarioDetail>(`/scenarios/${encodeURIComponent(key)}`);
}

export function startScenarioSession(scenarioKey: string) {
  return api<StartScenarioResult>("/scenarios/start", {
    method: "POST",
    body: JSON.stringify({ scenario_key: scenarioKey }),
  });
}

export function sendScenarioTurn(sessionId: string, message: string) {
  return api<ScenarioTurnResult>(`/scenarios/${sessionId}/turn`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function endScenarioSession(sessionId: string) {
  return api<ScenarioEndResult>(`/scenarios/${sessionId}/end`, {
    method: "POST",
  });
}

// ── Admin: custom scenario CRUD (SBL-US-06) ─────────────────────────────────
export interface CustomScenario {
  id: string;
  title: string;
  category: string;
  persona: string;
  intent: string;
  system_prompt: string;
  opening_line: string | null;
  target_vocab: string[];
  goal_type: "roleplay" | "negotiation";
  safety_mode: boolean;
  corporate_tone: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomScenarioInput {
  title: string;
  category: string;
  persona: string;
  intent: string;
  system_prompt: string;
  opening_line?: string;
  target_vocab: string[];
  goal_type: "roleplay" | "negotiation";
  safety_mode: boolean;
  corporate_tone: boolean;
}

export function adminListCustomScenarios() {
  return api<{ scenarios: CustomScenario[] }>("/scenarios/admin/custom");
}

export function adminCreateCustomScenario(data: CustomScenarioInput) {
  return api<CustomScenario>("/scenarios/admin/custom", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function adminUpdateCustomScenario(id: string, data: CustomScenarioInput) {
  return api<CustomScenario>(`/scenarios/admin/custom/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function adminDeleteCustomScenario(id: string) {
  return api<null>(`/scenarios/admin/custom/${id}`, {
    method: "DELETE",
  });
}
