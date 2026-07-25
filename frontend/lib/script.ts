import { api } from "./api";

export interface BaselineScores {
  structure: number;
  grammar: number;
  professional_tone: number;
  vocabulary: number;
  confidence: number;
  clarity: number;
  completeness: number;
}

export interface ProcessScriptRequest {
  submission: string;
  scenario_context?: string;
  language?: string;
}

export interface ProcessScriptResponse {
  script_id: string;
  baseline_status: string; // e.g. "completed", "Insufficient Data"
  baseline_scores: BaselineScores | null;
  rewrite_status: string; // "success", "minor_polish", "skipped", "failed"
  polished_rewrite: string | null;
  rewrite_note: string | null;
  newly_introduced_words: string[];
  category: string;
}

/**
 * Send submission text to backend Actionable Script processor to compute
 * baseline quality metrics (7 metrics) and generate a polished rewrite.
 */
export function processScript(data: ProcessScriptRequest): Promise<ProcessScriptResponse> {
  return api<ProcessScriptResponse>("/script/process", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
