"use client";

import * as React from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle,
  Clock,
  Lightbulb,
  Mic,
  Send,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

const SPEECH_TYPE_CONFIG: Record<string, { label: string; description: string; ideal_wpm: string }> = {
  business_pitch: {
    label: "Business Pitch",
    description: "Structure: Hook → Problem → Solution → Ask",
    ideal_wpm: "130-160 WPM",
  },
  casual_event: {
    label: "Casual Event Speech",
    description: "Focus on warmth, storytelling, and emotional connection",
    ideal_wpm: "120-150 WPM",
  },
  motivational: {
    label: "Motivational Speech",
    description: "Prioritize energy, tone variation, and strategic pausing",
    ideal_wpm: "130-160 WPM",
  },
  classroom: {
    label: "Classroom Presentation",
    description: "Include clear transitions and minimize filler words",
    ideal_wpm: "130-150 WPM",
  },
  ted_talk: {
    label: "TED-Style Talk",
    description: "Craft a narrative arc with personal stories",
    ideal_wpm: "130-150 WPM",
  },
};

export default function PublicSpeakingSessionPage() {
  const params = useParams();
  const router = useRouter();
  const speechType = params.speechType as string;
  const config = SPEECH_TYPE_CONFIG[speechType] || SPEECH_TYPE_CONFIG.business_pitch;

  const [inputMode, setInputMode] = React.useState<"audio" | "text">("audio");
  const [isRecording, setIsRecording] = React.useState(false);
  const [textContent, setTextContent] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [sessionId, setSessionId] = React.useState<string | null>(null);
  const [scorecard, setScorecard] = React.useState<any>(null);
  const [qaQuestion, setQaQuestion] = React.useState<string | null>(null);
  const [qaResponse, setQaResponse] = React.useState("");
  const [qaScore, setQaScore] = React.useState<any>(null);
  const [error, setError] = React.useState<string | null>(null);

  const mediaRecorderRef = React.useRef<MediaRecorder | null>(null);
  const audioChunksRef = React.useRef<Blob[]>([]);
  const audioBase64Ref = React.useRef<string | null>(null);
  const [hasRecording, setHasRecording] = React.useState(false);

  function blobToBase64(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve((reader.result as string).split(",")[1] ?? "");
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  const handleStartSession = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/api/public-speaking/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          speech_type: speechType,
          input_mode: inputMode,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Failed to start session");
      setSessionId(data.session_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start session");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitSpeech = async () => {
    if (!sessionId) return;
    if (inputMode === "audio" && !audioBase64Ref.current) {
      setError("Record your speech before submitting.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`/api/public-speaking/${sessionId}/turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          audio_data: inputMode === "audio" ? audioBase64Ref.current : null,
          text_content: inputMode === "text" ? textContent : null,
          is_final: true,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Failed to submit speech");
      setScorecard(data.scorecard);
      if (data.qa_triggered) {
        setQaQuestion(data.ai_question);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit speech");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitQaResponse = async () => {
    if (!sessionId) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await fetch(`/api/public-speaking/${sessionId}/qa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          audio_data: null,
          text_content: qaResponse,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Failed to submit Q&A response");
      setQaScore(data.qa_score);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit Q&A response");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleRecording = async () => {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
      return;
    }
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || "audio/webm" });
        audioBase64Ref.current = await blobToBase64(blob);
        setHasRecording(true);
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setHasRecording(false);
      setIsRecording(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Microphone permission denied.",
      );
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.back()}
          className="!w-9 shrink-0 !px-0"
        >
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="font-serif text-2xl font-semibold text-foreground">
            {config.label}
          </h1>
          <p className="text-sm text-muted-foreground">{config.description}</p>
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-2.5 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-foreground">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
          {error}
        </div>
      )}

      {!sessionId ? (
        <div className="flex flex-col gap-6 rounded-2xl border border-border bg-surface-elevated p-6">
          <div>
            <h2 className="font-semibold text-foreground">Session Setup</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Choose your input mode and start your practice session.
            </p>
          </div>

          <div className="flex gap-4">
            <button
              onClick={() => setInputMode("audio")}
              className={cn(
                "flex flex-1 flex-col items-center gap-3 rounded-xl border-2 p-4 transition-all",
                inputMode === "audio"
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50"
              )}
            >
              <Mic className="h-8 w-8 text-primary" />
              <div className="text-center">
                <div className="font-medium text-foreground">Voice</div>
                <div className="text-xs text-muted-foreground">Speak naturally</div>
              </div>
            </button>

            <button
              onClick={() => setInputMode("text")}
              className={cn(
                "flex flex-1 flex-col items-center gap-3 rounded-xl border-2 p-4 transition-all",
                inputMode === "text"
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50"
              )}
            >
              <Send className="h-8 w-8 text-primary" />
              <div className="text-center">
                <div className="font-medium text-foreground">Text</div>
                <div className="text-xs text-muted-foreground">Type your speech</div>
              </div>
            </button>
          </div>

          <div className="rounded-lg bg-muted/50 p-4">
            <div className="flex items-center gap-2 text-sm">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium text-foreground">Target Pace: {config.ideal_wpm}</span>
            </div>
          </div>

          <Button
            onClick={handleStartSession}
            disabled={isSubmitting}
            className="w-full"
          >
            {isSubmitting ? "Starting..." : "Start Session"}
          </Button>
        </div>
      ) : !scorecard ? (
        <div className="flex flex-col gap-6 rounded-2xl border border-border bg-surface-elevated p-6">
          <div>
            <h2 className="font-semibold text-foreground">Deliver Your Speech</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {inputMode === "audio"
                ? "Record your speech when ready. Speak clearly and at a natural pace."
                : "Type your speech below. Focus on structure and clarity."}
            </p>
          </div>

          {inputMode === "audio" ? (
            <div className="flex flex-col items-center gap-4 rounded-xl border-2 border-dashed border-border p-8">
              <button
                onClick={handleToggleRecording}
                className={cn(
                  "flex h-20 w-20 items-center justify-center rounded-full transition-all",
                  isRecording
                    ? "bg-danger text-white animate-pulse"
                    : "bg-primary text-white hover:scale-110"
                )}
              >
                <Mic className="h-10 w-10" />
              </button>
              <div className="text-center">
                <div className="font-medium text-foreground">
                  {isRecording ? "Recording..." : "Tap to Record"}
                </div>
                <div className="text-sm text-muted-foreground">
                  {isRecording ? "Speak clearly" : "Ready when you are"}
                </div>
              </div>
            </div>
          ) : (
            <Textarea
              label="Your speech"
              value={textContent}
              onChange={(e) => setTextContent(e.target.value)}
              placeholder="Type your speech here..."
              rows={8}
            />
          )}

          <Button
            onClick={handleSubmitSpeech}
            disabled={
              isSubmitting ||
              isRecording ||
              (inputMode === "text" ? !textContent.trim() : !hasRecording)
            }
            className="w-full"
          >
            {isSubmitting ? "Analyzing..." : "Submit for Analysis"}
          </Button>
        </div>
      ) : !qaQuestion ? (
        <div className="flex flex-col gap-6 rounded-2xl border border-border bg-surface-elevated p-6">
          <div className="flex items-center gap-3">
            <CheckCircle className="h-8 w-8 text-success" />
            <div>
              <h2 className="font-semibold text-foreground">Analysis Complete</h2>
              <p className="text-sm text-muted-foreground">
                Great job! Here's your performance breakdown.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <ScoreCard label="Overall" score={scorecard.overall_score} />
            <ScoreCard label="Pacing" score={scorecard.pacing} />
            <ScoreCard label="Tone" score={scorecard.tone_variation} />
            <ScoreCard label="Clarity" score={scorecard.voice_clarity} />
          </div>

          <div className="rounded-lg bg-muted/50 p-4">
            <div className="flex items-center gap-2 text-sm">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium text-foreground">
                Speaking Pace: {scorecard.words_per_minute?.toFixed(1)} WPM
              </span>
            </div>
          </div>

          {scorecard.filler_word_count > 0 && (
            <div className="rounded-lg bg-warning/10 border border-warning/20 p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-warning-foreground">
                <AlertCircle className="h-4 w-4" />
                <span>Filler Words: {scorecard.filler_word_count}</span>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                Try pausing silently instead of using "um" or "ah".
              </p>
            </div>
          )}

          <div className="rounded-lg bg-secondary/20 p-4">
            <div className="flex items-start gap-3">
              <Lightbulb className="mt-0.5 h-5 w-5 text-primary shrink-0" />
              <div>
                <div className="font-medium text-foreground">Key Feedback</div>
                <p className="mt-1 text-sm text-muted-foreground">{scorecard.summary}</p>
              </div>
            </div>
          </div>

          {scorecard.actionable_tips && scorecard.actionable_tips.length > 0 && (
            <div>
              <h3 className="font-medium text-foreground">Actionable Tips</h3>
              <ul className="mt-2 space-y-2">
                {scorecard.actionable_tips.map((tip: string, index: number) => (
                  <li key={index} className="flex items-start gap-2 text-sm text-muted-foreground">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                    {tip}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <Button onClick={() => router.push("/dashboard/public-speaking")} className="w-full">
            Try Another Speech Type
          </Button>
        </div>
      ) : !qaScore ? (
        <div className="flex flex-col gap-6 rounded-2xl border border-border bg-surface-elevated p-6">
          <div>
            <h2 className="font-semibold text-foreground">Audience Q&A</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              An audience member has a follow-up question. Respond impromptu.
            </p>
          </div>

          <div className="rounded-lg bg-secondary/20 p-4">
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-white shrink-0">
                ?
              </div>
              <div>
                <div className="font-medium text-foreground">Question</div>
                <p className="mt-1 text-sm text-foreground">{qaQuestion}</p>
              </div>
            </div>
          </div>

          <Textarea
            label="Your response"
            value={qaResponse}
            onChange={(e) => setQaResponse(e.target.value)}
            placeholder="Type your response..."
            rows={5}
          />

          <Button
            onClick={handleSubmitQaResponse}
            disabled={isSubmitting || !qaResponse.trim()}
            className="w-full"
          >
            {isSubmitting ? "Evaluating..." : "Submit Response"}
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-6 rounded-2xl border border-border bg-surface-elevated p-6">
          <div className="flex items-center gap-3">
            <CheckCircle className="h-8 w-8 text-success" />
            <div>
              <h2 className="font-semibold text-foreground">Q&A Evaluation</h2>
              <p className="text-sm text-muted-foreground">
                Here's how you handled the audience question.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <ScoreCard label="Composure" score={qaScore.composure} />
            <ScoreCard label="Relevance" score={qaScore.relevance} />
          </div>

          <div className="rounded-lg bg-secondary/20 p-4">
            <div className="flex items-start gap-3">
              <Lightbulb className="mt-0.5 h-5 w-5 text-primary shrink-0" />
              <div>
                <div className="font-medium text-foreground">Feedback</div>
                <p className="mt-1 text-sm text-muted-foreground">{qaScore.feedback}</p>
              </div>
            </div>
          </div>

          <Button onClick={() => router.push("/dashboard/public-speaking")} className="w-full">
            Back to Public Speaking Coach
          </Button>
        </div>
      )}
    </div>
  );
}

function ScoreCard({ label, score }: { label: string; score: number }) {
  const getColor = (score: number) => {
    if (score >= 80) return "text-success";
    if (score >= 60) return "text-warning";
    return "text-danger";
  };

  return (
    <div className="rounded-lg bg-muted/50 p-4 text-center">
      <div className="text-2xl font-bold text-foreground">{score}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
