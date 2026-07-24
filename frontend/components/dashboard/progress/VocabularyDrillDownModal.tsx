"use client";

import * as React from "react";
import { AlertTriangle, Sparkles, Volume2 } from "lucide-react";
import { Modal } from "@/components/ui/modal";
import { ApiError } from "@/lib/api";
import { playText } from "@/lib/tts";
import {
  getVocabularyDrillDown,
  type VocabularyDrillDown,
  type VocabularyWord,
  type VocabularyWordStatus,
} from "@/lib/vocabularyProgress";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 50;

type Filter = "all" | VocabularyWordStatus;

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "mastered", label: "Mastered" },
  { id: "learning", label: "Learning" },
];

interface VocabularyDrillDownModalProps {
  open: boolean;
  onClose: () => void;
}

/** PDG-US-12: Progress Dashboard - Vocabulary Growth Drill-down. */
export function VocabularyDrillDownModal({ open, onClose }: VocabularyDrillDownModalProps) {
  const [filter, setFilter] = React.useState<Filter>("all");
  const [drillDown, setDrillDown] = React.useState<VocabularyDrillDown | null>(null);
  const [words, setWords] = React.useState<VocabularyWord[]>([]);
  const [page, setPage] = React.useState(1);
  const [isLoading, setIsLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [playingWord, setPlayingWord] = React.useState<string | null>(null);
  const sentinelRef = React.useRef<HTMLDivElement>(null);
  // Guards against a slower, superseded request (e.g. the previous filter tab's
  // page 1) resolving after a newer one and overwriting it with stale words.
  const latestRequestId = React.useRef(0);

  const loadPage = React.useCallback(
    (targetPage: number, activeFilter: Filter, replace: boolean) => {
      const requestId = ++latestRequestId.current;
      setIsLoading(true);
      getVocabularyDrillDown({
        status: activeFilter === "all" ? undefined : activeFilter,
        page: targetPage,
        page_size: PAGE_SIZE,
      })
        .then((result) => {
          if (requestId !== latestRequestId.current) return;
          setDrillDown(result);
          setWords((prev) => (replace ? result.words : [...prev, ...result.words]));
          setPage(targetPage);
        })
        .catch((err) => {
          if (requestId !== latestRequestId.current) return;
          setError(err instanceof ApiError ? err.message : "Something went wrong.");
        })
        .finally(() => {
          if (requestId === latestRequestId.current) setIsLoading(false);
        });
    },
    [],
  );

  // Reset and reload whenever the modal opens or the filter changes.
  React.useEffect(() => {
    if (!open) return;
    setWords([]);
    setError(null);
    loadPage(1, filter, true);
  }, [open, filter, loadPage]);

  // E-04: infinite scroll — load the next 50 words as the sentinel enters view.
  React.useEffect(() => {
    if (!open || !drillDown?.has_more || isLoading) return;
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          loadPage(page + 1, filter, false);
        }
      },
      { threshold: 0.1 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [open, drillDown?.has_more, isLoading, page, filter, loadPage]);

  async function handlePlay(word: VocabularyWord) {
    setPlayingWord(word.word);
    await playText(word.word);
    setPlayingWord(null);
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Vocabulary Growth"
      description="Words you've used correctly in practice — 3+ uses moves a word to Mastered."
      className="max-w-lg"
    >
      <div className="flex flex-col gap-4">
        <div className="flex gap-1.5 rounded-xl bg-muted p-1">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => setFilter(f.id)}
              className={cn(
                "flex-1 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                filter === f.id
                  ? "bg-surface-elevated text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {f.label}
              {f.id === "mastered" && drillDown ? ` (${drillDown.mastered_count})` : null}
              {f.id === "learning" && drillDown ? ` (${drillDown.learning_count})` : null}
            </button>
          ))}
        </div>

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        {drillDown?.is_empty_state ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-border p-8 text-center">
            <Sparkles className="h-6 w-6 text-primary" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">
              Your vocabulary journey starts here. Complete a Scenario to start collecting words!
            </p>
          </div>
        ) : (
          <div className="flex max-h-[50vh] flex-col gap-2 overflow-y-auto">
            {words.map((word) => (
              <div
                key={word.word}
                className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface p-3"
              >
                <div className="flex flex-col gap-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium capitalize text-foreground">{word.word}</span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                        word.status === "mastered"
                          ? "bg-success/15 text-success"
                          : "bg-secondary text-secondary-foreground",
                      )}
                    >
                      {word.status}
                    </span>
                    {word.needs_review ? (
                      <span
                        className="flex items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-[10px] font-semibold text-warning"
                        title="Recently missed — could use another review"
                      >
                        <AlertTriangle className="h-2.5 w-2.5" aria-hidden="true" />
                        Needs Review
                      </span>
                    ) : null}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {word.phonetic_spelling} · used {word.use_count}x
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handlePlay(word)}
                  disabled={playingWord === word.word}
                  aria-label={`Hear pronunciation of ${word.word}`}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-surface-elevated hover:text-primary disabled:opacity-50"
                >
                  <Volume2 className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            ))}

            {drillDown?.has_more ? <div ref={sentinelRef} className="h-4" /> : null}
            {isLoading ? (
              <p className="py-2 text-center text-xs text-muted-foreground">Loading…</p>
            ) : null}
          </div>
        )}
      </div>
    </Modal>
  );
}
