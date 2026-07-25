"use client";

import * as React from "react";
import { Sparkles, TriangleAlert, RefreshCw, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { processScript, ProcessScriptResponse } from "@/lib/script";
import { ActionableScriptFeedback } from "@/components/script/ActionableScriptFeedback";

export default function ScriptPage() {
  const [submission, setSubmission] = React.useState("");
  const [scenarioContext, setScenarioContext] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [response, setResponse] = React.useState<ProcessScriptResponse | null>(null);
  const [lastSubmittedText, setLastSubmittedText] = React.useState("");

  async function handleSubmit(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!submission.trim()) return;

    setError(null);
    setIsSubmitting(true);
    try {
      const res = await processScript({
        submission: submission.trim(),
        scenario_context: scenarioContext.trim() || undefined,
        language: "en",
      });
      setResponse(res);
      setLastSubmittedText(submission.trim());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Request failed. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleReset() {
    setResponse(null);
    setError(null);
    setSubmission("");
  }

  const wordCount = submission.trim() ? submission.trim().split(/\s+/).length : 0;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      {/* Header */}
      <div>
        <h1 className="font-serif text-2xl font-semibold text-foreground sm:text-3xl">
          Actionable Script Rewriter
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Analyze your written transcript to receive instant baseline scores across 7 communication metrics and a polished, professional rewrite.
        </p>
      </div>

      {!response ? (
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {/* Submission Input Box */}
          <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-foreground flex items-center gap-2">
                <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
                Written Transcript
              </label>
              <span className="text-xs text-muted-foreground font-mono">
                {wordCount} {wordCount === 1 ? "word" : "words"}
              </span>
            </div>

            <div className="mt-3">
              <Textarea
                value={submission}
                onChange={(e) => setSubmission(e.target.value)}
                rows={6}
                placeholder="Paste or type your written response, interview answer, or session transcript here..."
                className="w-full"
              />
            </div>

            {/* Scenario Context */}
            <div className="mt-4">
              <Input
                label="Scenario Context (Optional)"
                placeholder="e.g. Technical Interview, Sales Pitch, Salary Negotiation"
                value={scenarioContext}
                onChange={(e) => setScenarioContext(e.target.value)}
              />
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="animate-fade-up flex items-start gap-3 rounded-2xl border border-danger/30 bg-danger/10 p-5 text-danger shadow-2xs">
              <TriangleAlert className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true" />
              <div className="flex flex-col gap-1">
                <h4 className="text-sm font-semibold text-foreground">Error</h4>
                <p className="text-xs text-danger font-medium leading-relaxed">{error}</p>
              </div>
            </div>
          )}

          {/* Submit Button */}
          <div className="flex justify-end">
            <Button
              type="submit"
              size="lg"
              loading={isSubmitting}
              disabled={!submission.trim()}
            >
              <Sparkles className="h-4 w-4 mr-2" aria-hidden="true" />
              Analyze & Generate Rewrite
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-col gap-6">
          <div className="flex justify-between items-center">
            <Button variant="outline" size="sm" onClick={handleReset}>
              <RefreshCw className="h-4 w-4 mr-2" aria-hidden="true" />
              Analyze Another Response
            </Button>
          </div>

          <ActionableScriptFeedback
            response={response}
            originalText={lastSubmittedText}
          />
        </div>
      )}
    </div>
  );
}
