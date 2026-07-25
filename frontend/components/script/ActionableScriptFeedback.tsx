"use client";

import * as React from "react";
import {
  Sparkles,
  TriangleAlert,
  Tag,
  CheckCircle2,
  AlertCircle,
  BookOpen,
} from "lucide-react";
import { ProcessScriptResponse } from "@/lib/script";
import { cn } from "@/lib/utils";

interface ActionableScriptFeedbackProps {
  response: ProcessScriptResponse;
  originalText?: string;
}

const SCORE_LABELS: Record<string, { label: string; description: string }> = {
  structure: {
    label: "Structure",
    description: "Flow, organization, and paragraph transitions",
  },
  grammar: {
    label: "Grammar",
    description: "Grammatical accuracy and sentence mechanics",
  },
  professional_tone: {
    label: "Professional Tone",
    description: "Appropriate formality and workplace resonance",
  },
  vocabulary: {
    label: "Vocabulary",
    description: "Range, precision, and domain terminology",
  },
  confidence: {
    label: "Confidence",
    description: "Assertiveness and absence of weak qualifiers",
  },
  clarity: {
    label: "Clarity",
    description: "Directness and ease of comprehension",
  },
  completeness: {
    label: "Completeness",
    description: "Thoroughness of answer relative to prompt length",
  },
};

/**
 * Render text with newly introduced words highlighted inline.
 */
function HighlightedRewrite({
  text,
  newWords,
}: {
  text: string;
  newWords: string[];
}) {
  if (!text) return null;
  if (!newWords || newWords.length === 0) {
    return <span className="whitespace-pre-wrap">{text}</span>;
  }

  const newWordsSet = new Set(newWords.map((w) => w.toLowerCase()));
  // Split text into word tokens and non-word separators preserving delimiters
  const tokens = text.split(/([a-zA-Z']+)/g);

  return (
    <span className="whitespace-pre-wrap leading-relaxed">
      {tokens.map((token, idx) => {
        const cleanWord = token.toLowerCase();
        if (newWordsSet.has(cleanWord)) {
          return (
            <mark
              key={idx}
              className="mx-0.5 inline-flex items-center rounded-md border border-primary/30 bg-primary/15 px-1.5 py-0.5 font-medium text-primary shadow-2xs dark:bg-primary/25"
              title="Newly introduced word"
            >
              {token}
            </mark>
          );
        }
        return <React.Fragment key={idx}>{token}</React.Fragment>;
      })}
    </span>
  );
}

export function ActionableScriptFeedback({
  response,
  originalText,
}: ActionableScriptFeedbackProps) {
  const {
    baseline_status,
    baseline_scores,
    rewrite_status,
    polished_rewrite,
    rewrite_note,
    newly_introduced_words,
    category,
  } = response;

  const isInsufficientData =
    baseline_status === "Insufficient Data" || rewrite_status === "skipped";

  return (
    <div className="flex flex-col gap-6">
      {/* Category Header Banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-surface-elevated p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <BookOpen className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h2 className="font-serif text-lg font-semibold text-foreground">
              Actionable Script Feedback
            </h2>
            <p className="text-xs text-muted-foreground">
              AI-driven baseline analysis and polished script alternative
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-foreground">
            <Tag className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
            Category: <strong className="text-primary">{category}</strong>
          </span>
        </div>
      </div>

      {/* 1. Baseline Scores Section */}
      <div className="animate-fade-up rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-serif text-lg font-semibold text-foreground">
              Baseline Metrics
            </h3>
            <p className="text-xs text-muted-foreground">
              Calculated for 7 core communication skills
            </p>
          </div>
          {baseline_status === "completed" && (
            <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-0.5 text-xs font-medium text-success">
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
              Assessed
            </span>
          )}
        </div>

        {isInsufficientData ? (
          <div className="mt-4 flex flex-col items-center justify-center rounded-xl border border-warning/30 bg-warning/10 p-6 text-center">
            <TriangleAlert className="h-8 w-8 text-warning" aria-hidden="true" />
            <h4 className="mt-2 text-base font-semibold text-foreground">
              Insufficient Data
            </h4>
            <p className="mt-1 max-w-md text-xs text-muted-foreground">
              {rewrite_note ||
                "Minimum 15 words required to calculate baseline metrics and generate a rewrite."}
            </p>
          </div>
        ) : baseline_scores ? (
          <div className="mt-5 grid grid-cols-2 gap-3.5 sm:grid-cols-4">
            {Object.entries(baseline_scores).map(([key, score]) => {
              const info = SCORE_LABELS[key] || {
                label: key.replace(/_/g, " "),
                description: "",
              };
              const scoreVal = Math.round(score);
              return (
                <div
                  key={key}
                  className="flex flex-col justify-between rounded-xl border border-border bg-surface p-4 transition-colors hover:border-primary/40"
                >
                  <div>
                    <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      {info.label}
                    </span>
                    <p className="mt-1 text-2xl font-bold text-foreground">
                      {scoreVal}
                      <span className="text-xs font-normal text-muted-foreground">
                        /100
                      </span>
                    </p>
                  </div>
                  <div className="mt-3">
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className={cn(
                          "h-1.5 rounded-full transition-all",
                          scoreVal >= 85
                            ? "bg-success"
                            : scoreVal >= 70
                              ? "bg-primary"
                              : "bg-warning"
                        )}
                        style={{ width: `${Math.min(100, Math.max(0, scoreVal))}%` }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}
      </div>

      {/* 2. Rewrite Display Section */}
      <div
        className="animate-fade-up rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm"
        style={{ animationDelay: "100ms" }}
      >
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" aria-hidden="true" />
            <h3 className="font-serif text-lg font-semibold text-foreground">
              Polished Rewrite
            </h3>
          </div>

          {/* Status badges */}
          {rewrite_status === "minor_polish" && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              Minor Polish — Original text was already strong
            </span>
          )}

          {rewrite_status === "success" && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-success/30 bg-success/10 px-3 py-1 text-xs font-medium text-success">
              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
              Enhanced Version
            </span>
          )}

          {rewrite_status === "skipped" && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-3 py-1 text-xs font-medium text-warning">
              <TriangleAlert className="h-3.5 w-3.5" aria-hidden="true" />
              Skipped
            </span>
          )}

          {rewrite_status === "failed" && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-danger/30 bg-danger/10 px-3 py-1 text-xs font-medium text-danger">
              <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
              Generation Failed
            </span>
          )}
        </div>

        {/* Note if provided */}
        {rewrite_note && rewrite_status !== "skipped" && (
          <p className="mt-3 rounded-lg bg-surface p-3 text-xs italic text-muted-foreground">
            {rewrite_note}
          </p>
        )}

        {/* Highlighted text or failure message */}
        {polished_rewrite ? (
          <div className="mt-4 flex flex-col gap-4">
            <div className="rounded-xl border border-border bg-surface p-5 text-sm text-foreground shadow-2xs">
              <HighlightedRewrite
                text={polished_rewrite}
                newWords={newly_introduced_words}
              />
            </div>

            {/* Newly Introduced Words List */}
            {newly_introduced_words && newly_introduced_words.length > 0 && (
              <div className="flex flex-col gap-2 rounded-xl bg-surface/50 p-4">
                <span className="text-xs font-medium text-muted-foreground">
                  Newly Introduced Terminology ({newly_introduced_words.length}):
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {newly_introduced_words.map((word, i) => (
                    <span
                      key={i}
                      className="inline-flex items-center rounded-md border border-primary/30 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary"
                    >
                      +{word}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          !isInsufficientData && (
            <div className="mt-4 rounded-xl border border-border bg-surface p-4 text-center text-xs text-muted-foreground">
              No rewrite generated.
            </div>
          )
        )}
      </div>

      {/* Comparison: Original Text if passed */}
      {originalText && (
        <div
          className="animate-fade-up rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm"
          style={{ animationDelay: "180ms" }}
        >
          <h3 className="font-serif text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Your Original Submission
          </h3>
          <p className="mt-2 rounded-xl bg-surface p-4 text-xs text-muted-foreground whitespace-pre-wrap leading-relaxed">
            {originalText}
          </p>
        </div>
      )}
    </div>
  );
}
