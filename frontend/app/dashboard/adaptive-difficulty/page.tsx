"use client";

import * as React from "react";
import {
  Target,
  Sparkles,
  TrendingUp,
  TrendingDown,
  ShieldCheck,
  Zap,
  RefreshCw,
  Copy,
  Check,
  AlertTriangle,
  Info,
  Clock,
  Send,
  Layers,
  Award,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  recordAttempt,
  generateDrill,
  getEscalationHistory,
  getMetricState,
  type MetricProgressionState,
  type EscalationHistoryResponse,
  type GenerateDrillResponse,
  type ScoredAttemptResponse,
} from "@/lib/adaptiveDifficulty";

function cn(...classes: (string | undefined | false | null)[]) {
  return classes.filter(Boolean).join(" ");
}

const PRESET_METRICS = [
  { id: "th_sound", label: "TH Sound (/θ/, /ð/)", category: "Phoneme" },
  { id: "rising_intonation", label: "Rising Intonation", category: "Pattern" },
  { id: "r_l_distinction", label: "R & L Distinction", category: "Phoneme" },
  { id: "vowel_clarity", label: "Vowel Clarity", category: "Pattern" },
];

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm", className)}>
      {children}
    </div>
  );
}

function StatusBadge({ children, variant }: { children: React.ReactNode; variant: "success" | "warn" | "info" | "neutral" | "danger" }) {
  const cls = {
    success: "bg-success/10 text-success border-success/20",
    warn: "bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400",
    info: "bg-primary/10 text-primary border-primary/20",
    neutral: "bg-muted text-muted-foreground border-border",
    danger: "bg-danger/10 text-danger border-danger/20",
  }[variant];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium", cls)}>
      {children}
    </span>
  );
}

export default function AdaptiveDifficultyPage() {
  const [selectedMetric, setSelectedMetric] = React.useState("th_sound");
  const [customMetric, setCustomMetric] = React.useState("");

  const [state, setState] = React.useState<MetricProgressionState | null>(null);
  const [history, setHistory] = React.useState<EscalationHistoryResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  // Drill Generator state
  const [drill, setDrill] = React.useState<GenerateDrillResponse | null>(null);
  const [generatingDrill, setGeneratingDrill] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  // Simulator state
  const [scoreInput, setScoreInput] = React.useState<number>(90);
  const [phraseInput, setPhraseInput] = React.useState<string>("Thirty-three thin turtles in the theater");
  const [submittingAttempt, setSubmittingAttempt] = React.useState(false);
  const [lastResult, setLastResult] = React.useState<ScoredAttemptResponse | null>(null);

  const activeMetricName = customMetric.trim() ? customMetric.trim().toLowerCase() : selectedMetric;

  const loadMetricData = React.useCallback(async (metricName: string) => {
    setLoading(true);
    setError(null);
    try {
      const [st, hist] = await Promise.all([
        getMetricState(metricName),
        getEscalationHistory(metricName),
      ]);
      setState(st);
      setHistory(hist);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load metric progression state.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadMetricData(activeMetricName);
  }, [activeMetricName, loadMetricData]);

  async function handleGenerateDrill() {
    setGeneratingDrill(true);
    try {
      const res = await generateDrill({ metric_name: activeMetricName });
      setDrill(res);
      setPhraseInput(res.drill_phrase);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate drill.");
    } finally {
      setGeneratingDrill(false);
    }
  }

  async function handleRecordAttempt(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!phraseInput.trim()) return;

    setSubmittingAttempt(true);
    setLastResult(null);
    try {
      const res = await recordAttempt({
        metric_name: activeMetricName,
        score: Number(scoreInput),
        drill_item: phraseInput.trim(),
      });
      setLastResult(res);
      await loadMetricData(activeMetricName);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to record attempt.");
    } finally {
      setSubmittingAttempt(false);
    }
  }

  function handleCopyPhrase() {
    if (!drill?.drill_phrase) return;
    navigator.clipboard.writeText(drill.drill_phrase);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      {/* Header */}
      <div>
        <h1 className="font-serif text-2xl font-semibold text-foreground sm:text-3xl">
          Adaptive Targeted Exercises
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Dynamic difficulty progression for accent, phoneme, and intonation patterns with anti-gaming mastery detection and regression handling.
        </p>
      </div>

      {/* Metric Selector Tabs */}
      <Card>
        <div className="flex flex-col gap-3">
          <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Select Target Accent / Pronunciation Metric
          </label>
          <div className="flex flex-wrap gap-2">
            {PRESET_METRICS.map((m) => (
              <button
                key={m.id}
                onClick={() => {
                  setSelectedMetric(m.id);
                  setCustomMetric("");
                  setLastResult(null);
                }}
                className={cn(
                  "flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-medium transition-all",
                  selectedMetric === m.id && !customMetric
                    ? "border-primary bg-primary/10 text-primary shadow-2xs"
                    : "border-border bg-surface text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
              >
                <Target className="h-3.5 w-3.5" />
                <span>{m.label}</span>
                <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  {m.category}
                </span>
              </button>
            ))}
          </div>

          <div className="mt-2 flex items-center gap-3">
            <span className="text-xs text-muted-foreground">Or enter custom metric:</span>
            <input
              type="text"
              placeholder="e.g. glottal_stop, stress_timing"
              value={customMetric}
              onChange={(e) => {
                setCustomMetric(e.target.value);
                setLastResult(null);
              }}
              className="h-8 flex-1 max-w-xs rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-hidden focus:ring-2 focus:ring-primary/20"
            />
          </div>
        </div>
      </Card>

      {/* Loading & Error Indicators */}
      {loading && (
        <div className="flex justify-center py-8">
          <span className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent text-primary" />
        </div>
      )}

      {error && (
        <div className="flex items-start gap-3 rounded-2xl border border-danger/30 bg-danger/10 p-5 text-danger shadow-2xs">
          <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
          <div className="flex flex-col gap-1">
            <h4 className="text-sm font-semibold">Error</h4>
            <p className="text-xs font-medium">{error}</p>
          </div>
        </div>
      )}

      {state && !loading && (
        <>
          {/* Main Status Dashboard Grid */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {/* Level Card */}
            <Card className="flex flex-col items-center justify-center text-center py-6">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary mb-2">
                <Layers className="h-6 w-6" />
              </span>
              <span className="text-3xl font-bold font-serif text-foreground">
                Level {state.current_level}
              </span>
              <span className="text-xs text-muted-foreground mt-1">
                Current Difficulty Level
              </span>
            </Card>

            {/* Consecutive Mastery Tracker */}
            <Card className="flex flex-col items-center justify-center text-center py-6">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500 mb-2">
                <Award className="h-6 w-6" />
              </span>
              <span className="text-3xl font-bold font-serif text-amber-500">
                {state.consecutive_mastery_count} / 3
              </span>
              <span className="text-xs text-muted-foreground mt-1">
                Consecutive High Scores (≥ 85%)
              </span>
            </Card>

            {/* Distinct Drill Items Tracker */}
            <Card className="flex flex-col items-center justify-center text-center py-6">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-success/10 text-success mb-2">
                <ShieldCheck className="h-6 w-6" />
              </span>
              <span className="text-3xl font-bold font-serif text-success">
                {new Set(state.recent_drill_items).size} Distinct
              </span>
              <span className="text-xs text-muted-foreground mt-1">
                Unique Phrases (≥2 required to level up)
              </span>
            </Card>
          </div>

          {/* Anti-gaming Alert Banner if 3 high scores are logged on single repeated item */}
          {state.consecutive_mastery_count >= 3 && new Set(state.recent_drill_items).size < 2 && (
            <div className="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
              <div className="flex flex-col gap-1 text-xs">
                <h4 className="text-sm font-semibold text-foreground">Anti-Gaming Threshold Active</h4>
                <p>
                  You have logged 3 consecutive high scores using the same repeated drill item. To level up to Level {state.current_level + 1}, generate or use a <strong>second distinct drill phrase</strong>.
                </p>
              </div>
            </div>
          )}

          {/* Generator Section */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                <h3 className="font-serif text-base font-semibold text-foreground">
                  AI Practice Drill Generator
                </h3>
              </div>
              <Button
                size="sm"
                onClick={handleGenerateDrill}
                loading={generatingDrill}
              >
                <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                Generate Level {state.current_level} Drill
              </Button>
            </div>

            {drill ? (
              <div className="flex flex-col gap-3 rounded-xl border border-primary/20 bg-primary/5 p-4">
                <div className="flex items-center justify-between">
                  <StatusBadge variant={drill.source === "llm" ? "info" : "neutral"}>
                    {drill.source === "llm" ? "Groq AI Generated" : "Static Fallback"}
                  </StatusBadge>
                  <Button variant="ghost" size="sm" onClick={handleCopyPhrase}>
                    {copied ? <Check className="h-3.5 w-3.5 text-success mr-1" /> : <Copy className="h-3.5 w-3.5 mr-1" />}
                    {copied ? "Copied" : "Copy Phrase"}
                  </Button>
                </div>
                <p className="font-serif text-lg font-medium text-foreground italic leading-snug">
                  &ldquo;{drill.drill_phrase}&rdquo;
                </p>
                <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                  <Info className="h-3.5 w-3.5 text-primary shrink-0" />
                  {drill.complexity_notes}
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-6 text-center text-xs text-muted-foreground border border-dashed border-border rounded-xl">
                <p>Click &ldquo;Generate Level {state.current_level} Drill&rdquo; to receive an AI-crafted targeted exercise phrase.</p>
              </div>
            )}
          </Card>

          {/* Attempt Scoring Simulator */}
          <Card>
            <div className="flex items-center gap-2 mb-4">
              <Send className="h-5 w-5 text-primary" />
              <div>
                <h3 className="font-serif text-base font-semibold text-foreground">
                  Scored Attempt Simulator
                </h3>
                <p className="text-xs text-muted-foreground">
                  Simulate an accent/phoneme attempt submission from an upstream scoring engine.
                </p>
              </div>
            </div>

            <form onSubmit={handleRecordAttempt} className="flex flex-col gap-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-medium text-foreground flex justify-between">
                    <span>Performance Score</span>
                    <span className="font-mono text-primary font-bold">{scoreInput}%</span>
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="1"
                    value={scoreInput}
                    onChange={(e) => setScoreInput(Number(e.target.value))}
                    className="h-2 rounded-lg bg-muted accent-primary cursor-pointer mt-2"
                  />
                </div>

                <div className="sm:col-span-2 flex flex-col gap-1.5">
                  <label className="text-xs font-medium text-foreground">
                    Drill Item / Sentence Used
                  </label>
                  <input
                    type="text"
                    value={phraseInput}
                    onChange={(e) => setPhraseInput(e.target.value)}
                    placeholder="Enter the phrase used in practice..."
                    className="h-9 rounded-lg border border-input bg-surface px-3 text-xs text-foreground focus:outline-hidden focus:ring-2 focus:ring-primary/20"
                  />
                </div>
              </div>

              {/* Simulation Preset Helpers */}
              <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border">
                <span className="text-xs text-muted-foreground font-medium">Quick Sim Presets:</span>
                <button
                  type="button"
                  onClick={() => {
                    setScoreInput(90);
                    setPhraseInput(`Distinct Drill Phrase ${Date.now().toString().slice(-4)}`);
                  }}
                  className="rounded-lg border border-success/30 bg-success/10 px-2.5 py-1 text-xs text-success hover:bg-success/20 transition-colors"
                >
                  High Score (90%) - Distinct Phrase
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setScoreInput(92);
                    setPhraseInput("Identical Repeated Phrase A");
                  }}
                  className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-600 dark:text-amber-400 hover:bg-amber-500/20 transition-colors"
                >
                  High Score (92%) - Same Phrase
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setScoreInput(45);
                    setPhraseInput("Difficult phrase attempt");
                  }}
                  className="rounded-lg border border-danger/30 bg-danger/10 px-2.5 py-1 text-xs text-danger hover:bg-danger/20 transition-colors"
                >
                  Low Score (45%) - Step Down
                </button>
              </div>

              <div className="flex justify-end">
                <Button type="submit" loading={submittingAttempt} disabled={!phraseInput.trim()}>
                  Submit Scored Attempt
                </Button>
              </div>
            </form>

            {/* Submission Result Feedback */}
            {lastResult && (
              <div className={cn(
                "mt-4 flex items-start gap-3 rounded-xl border p-4 text-xs font-medium animate-fade-up",
                lastResult.escalated
                  ? "border-success/30 bg-success/10 text-success"
                  : lastResult.regressed
                  ? "border-danger/30 bg-danger/10 text-danger"
                  : "border-primary/30 bg-primary/10 text-primary"
              )}>
                {lastResult.escalated ? (
                  <TrendingUp className="h-5 w-5 shrink-0 text-success mt-0.5" />
                ) : lastResult.regressed ? (
                  <TrendingDown className="h-5 w-5 shrink-0 text-danger mt-0.5" />
                ) : (
                  <Info className="h-5 w-5 shrink-0 text-primary mt-0.5" />
                )}
                <div className="flex flex-col gap-1">
                  <h4 className="font-semibold text-sm">
                    {lastResult.escalated
                      ? "Level Up Escalation!"
                      : lastResult.regressed
                      ? "Regression Step Down"
                      : "Attempt Logged"}
                  </h4>
                  <p>{lastResult.message}</p>
                </div>
              </div>
            )}
          </Card>

          {/* History Log Timeline */}
          {history && history.history.length > 0 && (
            <Card>
              <div className="flex items-center gap-2 mb-4">
                <Clock className="h-5 w-5 text-primary" />
                <h3 className="font-serif text-base font-semibold text-foreground">
                  Escalation & Progression Audit Log
                </h3>
              </div>

              <div className="relative space-y-3 pl-4 border-l-2 border-border">
                {history.history.map((evt, idx) => (
                  <div key={idx} className="relative flex flex-col gap-1">
                    <span className={cn(
                      "absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-background",
                      evt.event_type === "escalation"
                        ? "bg-success"
                        : evt.event_type === "regression"
                        ? "bg-danger"
                        : "bg-primary"
                    )} />
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-foreground">
                        {evt.event_type === "initial"
                          ? "Baseline Started"
                          : evt.event_type === "escalation"
                          ? `Escalated: Level ${evt.from_level} → Level ${evt.to_level}`
                          : `Regressed: Level ${evt.from_level} → Level ${evt.to_level}`}
                      </span>
                      <span className="text-[10px] font-mono text-muted-foreground">
                        {new Date(evt.reached_at).toLocaleString()}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">{evt.trigger_reason}</p>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
