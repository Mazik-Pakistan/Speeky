"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import { CheckCircle2, PhoneOff, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  endConversationSession,
  getConversationTranscript,
  sendConversationMessage,
  synthesizeSpeech,
  type ConversationTurn,
  type EndConversationResult,
} from "@/lib/conversation";

export default function ConversationSessionPage() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const [turns, setTurns] = React.useState<ConversationTurn[] | null>(null);
  const [topicLabel, setTopicLabel] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [isSending, setIsSending] = React.useState(false);
  const [isEnding, setIsEnding] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [playingIndex, setPlayingIndex] = React.useState<number | null>(null);
  const [summary, setSummary] = React.useState<EndConversationResult | null>(null);

  React.useEffect(() => {
    getConversationTranscript(params.sessionId)
      .then((data) => {
        setTurns(data.turns);
        setTopicLabel(data.topic_label);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Couldn't load this session."));
  }, [params.sessionId]);

  async function handleSend() {
    if (!message.trim() || isSending) return;
    setError(null);
    setIsSending(true);
    const text = message.trim();
    setMessage("");
    setTurns((prev) => [...(prev ?? []), { role: "user", content: text, input_mode: "text", correction_chip: null, created_at: "" }]);
    try {
      const result = await sendConversationMessage(params.sessionId, { text });
      setTurns((prev) => [
        ...(prev ?? []),
        { role: "assistant", content: result.reply, input_mode: null, correction_chip: null, created_at: "" },
      ]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSending(false);
    }
  }

  async function handlePlay(index: number, text: string) {
    setPlayingIndex(index);
    try {
      const blob = await synthesizeSpeech(text);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => setPlayingIndex(null);
      audio.onerror = () => setPlayingIndex(null);
      await audio.play();
    } catch {
      // Server TTS unavailable (e.g. Piper voice model not installed) — the
      // backend's own contract for this case is "the client falls back to
      // its own native TTS" (see Backend lib/tts_client.py), so use the
      // browser's built-in speech synthesis instead of failing silently.
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.onend = () => setPlayingIndex(null);
        utterance.onerror = () => setPlayingIndex(null);
        window.speechSynthesis.speak(utterance);
      } else {
        setPlayingIndex(null);
      }
    }
  }

  async function handleEnd() {
    setIsEnding(true);
    setError(null);
    try {
      const result = await endConversationSession(params.sessionId);
      setSummary(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsEnding(false);
    }
  }

  if (summary) {
    return (
      <div className="mx-auto flex max-w-xl flex-col gap-6">
        <div className="animate-fade-up rounded-2xl border border-border bg-gradient-to-br from-primary to-primary-hover p-8 text-center text-primary-foreground shadow-sm">
          <CheckCircle2 className="mx-auto h-6 w-6" aria-hidden="true" />
          <h1 className="mt-3 font-serif text-2xl font-semibold">Session Complete</h1>
          <p className="mt-2 text-sm text-primary-foreground/85">
            {Math.round(summary.duration_seconds)}s · Level: {summary.level}
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-border bg-surface-elevated p-4 text-center shadow-sm">
            <p className="text-xs text-muted-foreground">Fluency</p>
            <p className="mt-1 text-xl font-semibold text-foreground">
              {Math.round(summary.fluency_score)}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-surface-elevated p-4 text-center shadow-sm">
            <p className="text-xs text-muted-foreground">Vocabulary</p>
            <p className="mt-1 text-xl font-semibold text-foreground">
              {Math.round(summary.vocabulary_score)}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-surface-elevated p-4 text-center shadow-sm">
            <p className="text-xs text-muted-foreground">Pronunciation</p>
            <p className="mt-1 text-xl font-semibold text-foreground">
              {summary.pronunciation_score !== null ? Math.round(summary.pronunciation_score) : "—"}
            </p>
          </div>
        </div>
        {summary.new_memory_facts.length > 0 ? (
          <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
            <p className="text-sm font-medium text-foreground">Speeky remembered</p>
            <ul className="mt-2 flex flex-col gap-1 text-sm text-muted-foreground">
              {summary.new_memory_facts.map((fact, i) => (
                <li key={i}>
                  {fact.category}: {fact.value}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <Button size="lg" variant="outline" className="self-center" onClick={() => router.push("/dashboard/conversation")}>
          Start Another Conversation
        </Button>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="font-serif text-2xl font-semibold text-foreground">
          {topicLabel || "Conversation"}
        </h1>
        <Button size="sm" variant="outline" loading={isEnding} onClick={handleEnd}>
          <PhoneOff className="h-4 w-4" aria-hidden="true" />
          End Session
        </Button>
      </div>

      <div className="flex flex-col gap-4 rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
        <div className="flex max-h-[55vh] flex-col gap-4 overflow-y-auto">
          {(turns ?? []).map((turn, i) => (
            <div key={i} className={turn.role === "user" ? "ml-auto max-w-[80%]" : "max-w-[80%]"}>
              <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {turn.role === "user" ? "You" : "Coach"}
              </span>
              <div
                className={
                  turn.role === "user"
                    ? "rounded-xl rounded-tr-sm bg-primary px-4 py-3 text-sm text-primary-foreground"
                    : "flex items-start gap-2 rounded-xl rounded-tl-sm bg-secondary px-4 py-3 text-sm text-secondary-foreground"
                }
              >
                <span className="flex-1">{turn.content}</span>
                {turn.role === "assistant" ? (
                  <button
                    type="button"
                    onClick={() => handlePlay(i, turn.content)}
                    disabled={playingIndex === i}
                    aria-label="Play audio"
                    className="shrink-0 text-primary hover:opacity-70 disabled:animate-pulse"
                  >
                    <Volume2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                ) : null}
              </div>
              {turn.correction_chip ? (
                <div className="mt-1.5 rounded-lg bg-warning/10 px-3 py-2 text-xs text-foreground">
                  <span className="line-through opacity-70">{turn.correction_chip.original}</span>{" "}
                  <span className="font-medium text-success">{turn.correction_chip.corrected}</span>
                  <p className="mt-0.5 text-muted-foreground">{turn.correction_chip.explanation}</p>
                </div>
              ) : null}
            </div>
          ))}
        </div>

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex items-center gap-2 border-t border-border pt-4">
          <input
            type="text"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleSend();
              }
            }}
            placeholder="Type a message..."
            className="h-11 flex-1 rounded-xl border border-input bg-surface px-4 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-ring/40"
          />
          <Button size="md" loading={isSending} disabled={!message.trim()} onClick={handleSend}>
            Send
          </Button>
        </div>
      </div>
    </div>
  );
}
