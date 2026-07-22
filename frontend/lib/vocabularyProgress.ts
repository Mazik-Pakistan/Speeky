import { api } from "./api";

// ── Types (mirrors Backend/services/vocabulary_progress_service.py response shapes) ─

export type VocabularyWordStatus = "learning" | "mastered";

export interface VocabularyWord {
  word: string;
  use_count: number;
  status: VocabularyWordStatus;
  needs_review: boolean;
  last_used_at: string;
  phonetic_spelling: string;
}

export interface VocabularyDrillDown {
  is_empty_state: boolean;
  mastered_count: number;
  learning_count: number;
  words: VocabularyWord[];
  page: number;
  page_size: number;
  has_more: boolean;
}

export function getVocabularyDrillDown(
  params: { status?: VocabularyWordStatus; page?: number; page_size?: number } = {}
) {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  const qs = query.toString();
  return api<VocabularyDrillDown>(`/vocabulary-progress/drill-down${qs ? `?${qs}` : ""}`);
}

export function getVocabularyWordDetail(word: string) {
  return api<VocabularyWord>(`/vocabulary-progress/words/${encodeURIComponent(word)}`);
}
