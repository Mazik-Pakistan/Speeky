import { api } from "./api";

// Post-Session Actionable Script — Rewrite trio
//   US-158 generate  /  US-156 score  /  US-159 explain

export type DifficultyLevel = "beginner" | "intermediate" | "advanced" | "executive";

export const DIFFICULTY_LABELS: Record<DifficultyLevel, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
  executive: "Executive",
};

// US-158 -------------------------------------------------------------------
export interface GenerateRewriteResult {
  original: string;
  rewrite: string;
  difficulty_used: DifficultyLevel;
  auto_detected: boolean;
  generated_by: "llm" | "offline";
}

export function generateRewrite(
  original: string,
  opts: { difficulty?: DifficultyLevel; context?: string } = {},
) {
  return api<GenerateRewriteResult>("/rewrite/generate", {
    method: "POST",
    body: JSON.stringify({
      original,
      difficulty: opts.difficulty ?? null,
      context: opts.context ?? null,
    }),
  });
}

// US-156 -------------------------------------------------------------------
export interface DimensionScore {
  name: string;
  score: number;
  explanation: string;
}

export interface ScoreRewriteResult {
  overall_score: number;
  dimensions: DimensionScore[];
  summary: string;
  significant_improvement: boolean;
  graded_by: "llm" | "offline";
}

export function scoreRewrite(original: string, rewrite: string) {
  return api<ScoreRewriteResult>("/rewrite/score", {
    method: "POST",
    body: JSON.stringify({ original, rewrite }),
  });
}

// US-159 -------------------------------------------------------------------
export interface ChangeExplanation {
  category: string;
  before: string;
  after: string;
  explanation: string;
}

export interface ExplainRewriteResult {
  changes: ChangeExplanation[];
  summary: string;
  has_meaningful_changes: boolean;
  explained_by: "llm" | "offline";
}

export function explainRewrite(original: string, rewrite: string) {
  return api<ExplainRewriteResult>("/rewrite/explain", {
    method: "POST",
    body: JSON.stringify({ original, rewrite }),
  });
}

// Human-readable dimension/category labels for the UI.
export const DIMENSION_LABELS: Record<string, string> = {
  grammar: "Grammar",
  professional_tone: "Professional Tone",
  vocabulary: "Vocabulary",
  sentence_organization: "Sentence Organization",
  conciseness: "Conciseness",
};

export const CATEGORY_LABELS: Record<string, string> = {
  grammar: "Grammar",
  vocabulary: "Vocabulary",
  tone: "Tone",
  conciseness: "Conciseness",
  structure: "Structure",
};
