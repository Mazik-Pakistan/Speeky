"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { CheckCircle2, Headphones, Lock, Sparkles, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  endScenarioSession,
  getScenarioDetail,
  sendScenarioTurn,
  startScenarioSession,
  type ScenarioDetail,
  type ScenarioEndResult,
  type StartScenarioResult,
} from "@/lib/scenario";
import { useAutoScroll } from "@/lib/useAutoScroll";
import { useAutoSpeak } from "@/lib/useAutoSpeak";

interface ChatTurn {
  role: "assistant" | "user";
  content: string;
}

type Step =
  | { name: "loading" }
  | { name: "locked"; message: string }
  | { name: "error"; message: string }
  | { name: "intro"; detail: ScenarioDetail }
  | {
      name: "chat";
      session: StartScenarioResult;
      turns: ChatTurn[];
      endedEarly: boolean;
    }
  | { name: "results"; result: ScenarioEndResult };

export default function ScenarioSessionPage() {
  const params = useParams<{ key: string }>();
  const router = useRouter();
  const [step, setStep] = React.useState<Step>({ name: "loading" });
  const [chatInput, setChatInput] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [audioMode, setAudioMode] = React.useState(false);
  const chatTurns = step.name === "chat" ? step.turns : null;
  const scrollRef = useAutoScroll(chatTurns?.length ?? 0);
  useAutoSpeak(audioMode, chatTurns);

  React.useEffect(() => {
    let cancelled = false;
    getScenarioDetail(params.key)
      .then((detail) => {
        if (!cancelled) setStep({ name: "intro", detail });
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 403) {
          setStep({ name: "locked", message: err.message });
        } else {
          setStep({
            name: "error",
            message: err instanceof ApiError ? err.message : "Couldn't load this scenario.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [params.key]);

  async function handleStart() {
    if (step.name !== "intro") return;
    setError(null);
    setIsSubmitting(true);
    try {
      const session = await startScenarioSession(params.key);
      setStep({
        name: "chat",
        session,
        turns: [{ role: "assistant", content: session.opening_message }],
        endedEarly: false,
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start this scenario.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSendChat() {
    if (step.name !== "chat" || !chatInput.trim() || isSubmitting) return;
    setError(null);
    setIsSubmitting(true);
    const message = chatInput.trim();
    setChatInput("");
    try {
      const result = await sendScenarioTurn(step.session.session_id, message);
      setStep({
        ...step,
        turns: [
          ...step.turns,
          { role: "user", content: message },
          { role: "assistant", content: result.reply },
        ],
        endedEarly: result.status === "ended_early",
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleEnd() {
    if (step.name !== "chat") return;
    setError(null);
    setIsSubmitting(true);
    try {
      const result = await endScenarioSession(step.session.session_id);
      setStep({ name: "results", result });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (step.name === "loading") {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <span
          className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent text-muted-foreground"
          aria-hidden="true"
        />
      </div>
    );
  }

  if (step.name === "locked") {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-4 rounded-2xl border border-warning/30 bg-warning/10 p-8 text-center">
        <Lock className="h-6 w-6 text-warning" aria-hidden="true" />
        <p className="text-sm text-foreground">{step.message}</p>
        <Button href="/dashboard/assessment" size="sm">
          Complete Assessment
        </Button>
      </div>
    );
  }

  if (step.name === "error") {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-4 rounded-2xl border border-danger/30 bg-danger/5 p-8 text-center">
        <TriangleAlert className="h-6 w-6 text-danger" aria-hidden="true" />
        <p className="text-sm text-foreground">{step.message}</p>
        <Button href="/dashboard/explore" size="sm">
          Back to Explore
        </Button>
      </div>
    );
  }

  if (step.name === "intro") {
    const { detail } = step;
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-6">
        <div>
          <h1 className="font-serif text-2xl font-semibold text-foreground">{detail.label}</h1>
          <p className="mt-1 text-sm text-muted-foreground">Roleplay persona: {detail.persona}</p>
        </div>
        <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
          <p className="text-sm text-foreground">{detail.intent}</p>
          <div className="mt-5">
            <p className="text-sm font-medium text-foreground">Target vocabulary</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {detail.target_vocab.map((word) => (
                <span
                  key={word}
                  className="rounded-full bg-secondary px-3 py-1 text-xs font-medium text-secondary-foreground"
                >
                  {word}
                </span>
              ))}
            </div>
          </div>
          {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
          <Button size="lg" className="mt-6" loading={isSubmitting} onClick={handleStart}>
            Start Scenario
          </Button>
        </div>
      </div>
    );
  }

  if (step.name === "chat") {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        <div className="flex items-center justify-between">
          <h1 className="font-serif text-2xl font-semibold text-foreground">
            {step.session.label}
          </h1>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setAudioMode((v) => !v)}
              aria-pressed={audioMode}
              aria-label={audioMode ? "Turn off audio mode" : "Turn on audio mode"}
              title={audioMode ? "Audio mode on — replies are spoken automatically" : "Turn on audio mode"}
              className={
                "flex h-9 w-9 items-center justify-center rounded-xl border transition-colors " +
                (audioMode
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-surface text-muted-foreground hover:text-foreground")
              }
            >
              <Headphones className="h-4 w-4" aria-hidden="true" />
            </button>
            <Button size="sm" variant="outline" loading={isSubmitting} onClick={handleEnd}>
              End Scenario
            </Button>
          </div>
        </div>

        <div className="flex flex-col gap-4 rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
          <div ref={scrollRef} className="flex max-h-[50vh] flex-col gap-4 overflow-y-auto">
            {step.turns.map((turn, i) => (
              <div
                key={i}
                className={turn.role === "user" ? "ml-auto max-w-[80%]" : "max-w-[80%]"}
              >
                <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {turn.role === "user" ? "You" : step.session.persona}
                </span>
                <div
                  className={
                    turn.role === "user"
                      ? "rounded-xl rounded-tr-sm bg-primary px-4 py-3 text-sm text-primary-foreground"
                      : "rounded-xl rounded-tl-sm bg-secondary px-4 py-3 text-sm text-secondary-foreground"
                  }
                >
                  {turn.content}
                </div>
              </div>
            ))}
          </div>

          {step.endedEarly ? (
            <p className="text-sm text-warning">
              This scenario ended early. Click &quot;End Scenario&quot; to see your results.
            </p>
          ) : (
            <div className="flex items-center gap-2 border-t border-border pt-4">
              <input
                type="text"
                value={chatInput}
                onChange={(event) => setChatInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    handleSendChat();
                  }
                }}
                placeholder="Type your response..."
                className="h-11 flex-1 rounded-xl border border-input bg-surface px-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
              <Button
                size="md"
                loading={isSubmitting}
                disabled={!chatInput.trim()}
                onClick={handleSendChat}
              >
                Send
              </Button>
            </div>
          )}
          {error ? <p className="text-sm text-danger">{error}</p> : null}
        </div>
      </div>
    );
  }

  // step.name === "results"
  const { result } = step;
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div className="animate-fade-up rounded-2xl border border-border bg-gradient-to-br from-primary to-primary-hover p-8 text-center text-primary-foreground shadow-sm">
        <Sparkles className="mx-auto h-6 w-6" aria-hidden="true" />
        <h1 className="mt-3 font-serif text-2xl font-semibold">
          {Math.round(result.scores.politeness ?? 0)}/100 Politeness
        </h1>
        <p className="mt-2 text-sm text-primary-foreground/85">{result.summary}</p>
      </div>

      <div
        className="animate-fade-up rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm"
        style={{ animationDelay: "100ms" }}
      >
        <h2 className="font-serif text-lg font-semibold text-foreground">Scores</h2>
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3">
          {Object.entries(result.scores)
            .filter(([, value]) => value !== null)
            .map(([key, value]) => (
              <div key={key} className="rounded-xl border border-border bg-surface p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {key.replace(/_/g, " ")}
                </p>
                <p className="mt-1 text-xl font-semibold text-foreground">{Math.round(value ?? 0)}</p>
              </div>
            ))}
        </div>
        {result.met_goal !== null ? (
          <div
            className={
              "mt-4 flex items-center gap-2 rounded-xl px-4 py-3 text-sm " +
              (result.met_goal ? "bg-success/10 text-success" : "bg-warning/10 text-warning")
            }
          >
            {result.met_goal ? (
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
            ) : (
              <TriangleAlert className="h-4 w-4" aria-hidden="true" />
            )}
            {result.met_goal ? "You achieved the scenario goal." : "You didn't fully achieve the scenario goal this time."}
          </div>
        ) : null}
      </div>

      <div
        className="animate-fade-up rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm"
        style={{ animationDelay: "180ms" }}
      >
        <h2 className="font-serif text-lg font-semibold text-foreground">Target Vocabulary</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {result.vocab_used.map((word) => (
            <span
              key={word}
              className="rounded-full bg-success/15 px-3 py-1 text-xs font-medium text-success"
            >
              {word}
            </span>
          ))}
          {result.vocab_missing.map((word) => (
            <span
              key={word}
              className="rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground"
            >
              {word}
            </span>
          ))}
        </div>
        {result.suggestion ? (
          <p className="mt-4 text-sm text-muted-foreground">{result.suggestion}</p>
        ) : null}
      </div>

      <Button
        size="lg"
        variant="outline"
        className="self-center"
        onClick={() => router.push("/dashboard/explore")}
      >
        Back to Explore
      </Button>
    </div>
  );
}
