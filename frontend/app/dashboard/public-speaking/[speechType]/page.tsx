"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle,
  Clock,
  Lightbulb,
  Mic,
  Send,
  AlertCircle,
  Video,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useVoiceReadinessGate } from "@/components/common/VoiceReadinessGate";
import { useCameraReadinessGate } from "@/components/common/CameraReadinessGate";
import { MilestoneCelebrationModal } from "@/components/dashboard/MilestoneCelebrationModal";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { FillerWordsScorecardSection } from "@/components/dashboard/public-speaking/FillerWordsScorecardSection";
import { DeliverySparkline } from "@/components/dashboard/public-speaking/DeliverySparkline";
/**
 * Lazy: @livekit/components-react is ~150kB and only a fraction of sessions open the
 * face-to-face Q&A at all. Imported statically it landed in this page's bundle for everyone,
 * taking First Load from 137kB to 288kB — the same mistake the MediaPipe loader avoids by
 * splitting the vision runtime into its own async chunk.
 *
 * ssr:false because LiveKit touches browser media APIs on import.
 */
const QaAvatarCall = dynamic(
  () =>
    import("@/components/dashboard/public-speaking/QaAvatarCall").then((m) => m.QaAvatarCall),
  { ssr: false },
);
const IdleAudiencePanel = dynamic(
  () =>
    import("@/components/dashboard/public-speaking/IdleAudiencePanel").then(
      (m) => m.IdleAudiencePanel,
    ),
  { ssr: false },
);
import { ApiError } from "@/lib/api";
import {
  startPublicSpeakingSession,
  submitPublicSpeakingTurn,
  submitPublicSpeakingQa,
  type PublicSpeakingScorecard,
  type SpeechType,
} from "@/lib/publicSpeaking";
import { buildVoiceWsUrl, useVoiceSocket, type VoiceFeatures } from "@/lib/useVoiceSocket";
import { usePracticeTimePing } from "@/lib/usePracticeTimePing";
import { useVideoAnalysis } from "@/lib/vision/useVideoAnalysis";
import type { GazeBucket } from "@/lib/vision/gaze";
import type { FramingState } from "@/lib/vision/types";

/** Short, live-overlay phrasing — terser than the calibration modal's copy, since this shows
 *  during active recording and must not compete with the transcript for attention. Framing
 *  takes priority over gaze: a bad gaze reading is meaningless until framing is fixed. */
const LIVE_FRAMING_HINTS: Partial<Record<FramingState, string>> = {
  too_close: "Move back a little",
  too_far: "Move a little closer",
  off_center: "Centre yourself in frame",
  shoulders_cropped: "Tilt your screen back",
};

const LIVE_GAZE_HINTS: Partial<Record<GazeBucket, string>> = {
  down: "Try looking up at the camera",
  up: "Try looking at the camera",
  side: "Try looking at the camera",
  offscreen: "You're out of frame",
};

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
  // Opt-in, off by default, and only meaningful alongside voice. Enabling it routes Start
  // Session through the camera gate, which is what produces the gaze calibration; skip that and
  // the payload reports itself as uncalibrated and the results tile withholds its numbers.
  const [cameraEnabled, setCameraEnabled] = React.useState(false);
  const [textContent, setTextContent] = React.useState("");
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [sessionId, setSessionId] = React.useState<string | null>(null);
  const [scorecard, setScorecard] = React.useState<any>(null);
  const [qaQuestion, setQaQuestion] = React.useState<string | null>(null);
  const [qaResponse, setQaResponse] = React.useState("");
  const [qaScore, setQaScore] = React.useState<any>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [showQa, setShowQa] = React.useState(false);
  // Both avatar panels are opt-in. The Q&A one talks, so it is Q&A-only: during the speech it
  // would talk over the speaker and its voice would reach the mic feeding the audio scorer. The
  // backend refuses a "qa" token before qa_phase regardless.
  const [qaCallActive, setQaCallActive] = React.useState(false);
  // The speech-phase one is silent — no STT, LLM or TTS exist in that room — so it is presence
  // to speak to, with nothing to talk over and nothing listening. Gated on in_progress instead.
  const [idleAudienceActive, setIdleAudienceActive] = React.useState(false);

  const sessionIdRef = React.useRef<string | null>(null);
  sessionIdRef.current = sessionId;
  const voiceStartedAt = React.useRef<number | null>(null);
  const voiceDurationRef = React.useRef<number>(0);
  const featuresRef = React.useRef({
    has: false,
    word_timings: [] as { word: string; start: number; end: number }[],
    duration_seconds: 0,
    avg_db: undefined as number | undefined,
    pitch_range_semitones: 0,
    snr_db: undefined as number | undefined,
    mean_pitch_hz: undefined as number | undefined,
    intensity_variation_db: 0,
  });
  const getWsUrl = React.useCallback(() => {
    const id = sessionIdRef.current;
    if (!id) return null;
    return buildVoiceWsUrl(`/public-speaking/${id}/voice-ws`);
  }, []);

  // Live text is spliced directly into the (editable) textarea instead of a separate
  // preview line — but the textarea is editable at any time, so a naive splice risks
  // clobbering an in-progress edit. committedTextRef is the "locked" baseline (real,
  // finalized transcript text, or whatever the user typed); splicedPartialRef is the
  // live guess currently appended after it, or null when no live guess is showing.
  // Each update only touches the textarea if its current value still exactly matches
  // what we last spliced — the moment the user types anything, both callbacks back off
  // and leave their edit alone until the next utterance starts.
  const committedTextRef = React.useRef("");
  const splicedPartialRef = React.useRef<string | null>(null);

  const onPartial = React.useCallback((text: string) => {
    if (!text) return;
    setTextContent((current) => {
      const base = committedTextRef.current;
      const expected =
        splicedPartialRef.current === null ? base : `${base}${base ? " " : ""}${splicedPartialRef.current}`;
      if (current !== expected) return current; // user has edited — leave it alone
      if (splicedPartialRef.current === null) committedTextRef.current = current; // snapshot baseline
      splicedPartialRef.current = text;
      return `${committedTextRef.current}${committedTextRef.current ? " " : ""}${text}`;
    });
  }, []);

  const {
    isVoiceActive,
    isConnectingVoice,
    isStoppingVoice,
    voiceStatus,
    error: voiceError,
    startVoice,
    stopVoice,
  } = useVoiceSocket(
    getWsUrl,
    (text, features?: VoiceFeatures) => {
      setTextContent((prev) => {
        const base = committedTextRef.current;
        const expected =
          splicedPartialRef.current === null ? null : `${base}${base ? " " : ""}${splicedPartialRef.current}`;
        // Still showing our own live guess untouched? Replace it with the real text
        // instead of appending on top of the guess. Otherwise (no live guess, or the
        // user edited) fall back to the original append-to-whatever's-there behavior.
        const from = expected !== null && prev === expected ? base : prev;
        const next = from.trim() ? `${from.trim()} ${text}` : text;
        committedTextRef.current = next; // locked
        splicedPartialRef.current = null; // ready for the next utterance
        return next;
      });
      if (features) {
        const acc = featuresRef.current;
        if (features.word_timings) acc.word_timings.push(...features.word_timings);
        if (typeof features.duration_seconds === "number") acc.duration_seconds += features.duration_seconds;
        if (typeof features.avg_db === "number") acc.avg_db = features.avg_db;
        if (typeof features.pitch_range_semitones === "number")
          acc.pitch_range_semitones = Math.max(acc.pitch_range_semitones, features.pitch_range_semitones);
        // Worst SNR across the session, not the last one: a single noisy utterance is the
        // clarity problem worth surfacing, and taking the latest would hide it.
        if (typeof features.snr_db === "number")
          acc.snr_db = acc.snr_db === undefined ? features.snr_db : Math.min(acc.snr_db, features.snr_db);
        if (typeof features.mean_pitch_hz === "number") acc.mean_pitch_hz = features.mean_pitch_hz;
        if (typeof features.intensity_variation_db === "number")
          acc.intensity_variation_db = Math.max(
            acc.intensity_variation_db,
            features.intensity_variation_db,
          );
        acc.has = true;
      }
    },
    onPartial,
  );
  const { gate: voiceGate, runWithVoiceReadiness } = useVoiceReadinessGate({
    featureName: "Public Speaking Practice",
  });
  const {
    gate: cameraGate,
    runWithCameraReadiness,
    calibration,
  } = useCameraReadinessGate({ featureName: "delivery analysis" });

  const {
    isVideoActive,
    isStartingVideo,
    videoStatus,
    error: videoError,
    loadProgress,
    startVideo,
    stopVideo,
    videoRef,
    getVideoFeatures,
    liveFraming,
    liveGazeBucket,
    gazeScorable,
  } = useVideoAnalysis({ calibration: calibration ?? undefined });

  const liveVisualHint = isVideoActive
    ? (LIVE_FRAMING_HINTS[liveFraming] ??
      (liveGazeBucket ? LIVE_GAZE_HINTS[liveGazeBucket] : undefined))
    : undefined;

  // PDG-US-15: heartbeat pings while this speech is the active practice
  // session, crediting lifetime practice time and surfacing any milestone
  // that unlocks mid-session. "Active" until scored, and — if a follow-up
  // Q&A got triggered — until that's answered too.
  const isSessionDone = scorecard !== null && (qaQuestion === null || qaScore !== null);
  const { newlyUnlocked, dismissMilestone } = usePracticeTimePing(
    "public_speaking",
    sessionId,
    sessionId !== null && !isSessionDone,
  );

  const handleStartVoice = async () => {
    if (isVoiceActive) return;
    voiceStartedAt.current = performance.now();
    committedTextRef.current = textContent;
    splicedPartialRef.current = null;
    // Camera first: if it fails we still want the speech recorded. useVideoAnalysis swallows
    // its own failures into `videoError`, so this never blocks the voice path.
    if (cameraEnabled) await startVideo();
    await startVoice();
  };

  const handleStopVoice = async () => {
    await stopVoice();
    if (isVideoActive) await stopVideo();
    if (voiceStartedAt.current != null) {
      voiceDurationRef.current += (performance.now() - voiceStartedAt.current) / 1000;
      voiceStartedAt.current = null;
    }
  };

  const handleStartSession = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const data = await startPublicSpeakingSession({
        speech_type: speechType as SpeechType,
        input_mode: inputMode === "audio" && cameraEnabled ? "audio_video" : inputMode,
      });
      setSessionId(data.session_id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to start session");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitSpeech = async () => {
    if (!sessionId) return;
    if (isVoiceActive) await handleStopVoice();
    // Submitting flips the session to qa_phase, which invalidates the idle room's own gate.
    // Close it here rather than letting the branch switch unmount it, so teardown is ordered.
    setIdleAudienceActive(false);
    const content = textContent.trim();
    if (!content) {
      setError(
        inputMode === "audio"
          ? "Record your speech before submitting."
          : "Enter your speech before submitting.",
      );
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const f = featuresRef.current;
      // Consume-once, exactly like the audio features above. stopVideo() has already run via
      // handleStopVoice, so the aggregate is built and the camera is released by now.
      const video = getVideoFeatures();
      const data = await submitPublicSpeakingTurn(sessionId, {
        text_content: content,
        duration_seconds:
          inputMode === "audio"
            ? Math.max(1, f.duration_seconds || voiceDurationRef.current)
            : null,
        audio_features: f.has
          ? {
              word_timings: f.word_timings,
              avg_db: f.avg_db,
              pitch_range_semitones: f.pitch_range_semitones,
              snr_db: f.snr_db,
              mean_pitch_hz: f.mean_pitch_hz,
              intensity_variation_db: f.intensity_variation_db,
              duration_seconds: f.duration_seconds,
            }
          : undefined,
        video_features: video ?? undefined,
        is_final: true,
      });
      setScorecard(data.scorecard);
      if (data.qa_triggered) {
        setQaQuestion(data.ai_question ?? null);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to submit speech");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitQaResponse = async () => {
    if (!sessionId) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const data = await submitPublicSpeakingQa(sessionId, {
        audio_data: null,
        text_content: qaResponse,
      });
      setQaScore(data.qa_score);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to submit Q&A response");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {voiceGate}
      {cameraGate}
      <MilestoneCelebrationModal
        milestone={newlyUnlocked[0] ?? null}
        onClose={() => newlyUnlocked[0] && dismissMilestone(newlyUnlocked[0].hours)}
      />
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
          <h1 className="font-serif text-h2 font-semibold text-foreground">
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

          {/* Camera is an add-on to Voice, never a mode of its own — physical delivery is only
              meaningful alongside a spoken turn. Off by default; the consent line stays visible
              rather than hiding behind a modal, because it is the whole basis for trusting this. */}
          <label
            className={cn(
              "flex cursor-pointer gap-3 rounded-xl border-2 p-4 transition-all",
              inputMode !== "audio" && "cursor-not-allowed opacity-50",
              cameraEnabled && inputMode === "audio"
                ? "border-primary bg-primary/5"
                : "border-border",
            )}
          >
            <input
              type="checkbox"
              checked={cameraEnabled && inputMode === "audio"}
              disabled={inputMode !== "audio"}
              onChange={(e) => setCameraEnabled(e.target.checked)}
              className="mt-1 h-4 w-4 shrink-0 accent-[var(--color-primary)]"
            />
            <div className="flex flex-col gap-1">
              <span className="flex items-center gap-2 font-medium text-foreground">
                <Video className="h-4 w-4 text-primary" />
                Also analyse my body language
                <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-normal text-muted-foreground">
                  Beta
                </span>
              </span>
              <span className="text-xs text-muted-foreground">
                {inputMode === "audio"
                  ? "Your camera feed never leaves this device. We analyse it in your browser and only send a summary — no video, no images, and no frame data are uploaded or stored."
                  : "Available with Voice input."}
              </span>
            </div>
          </label>

          <div className="rounded-lg bg-muted/50 p-4">
            <div className="flex items-center gap-2 text-sm">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium text-foreground">Target Pace: {config.ideal_wpm}</span>
            </div>
          </div>

          <Button
          onClick={
            inputMode !== "audio"
              ? handleStartSession
              : cameraEnabled
                // Voice first (required modality), camera second (optional add-on). The camera
                // gate is only invoked when the user opted in — prompting for a webcam during a
                // voice-only session would be an unpleasant surprise.
                ? () =>
                    void runWithVoiceReadiness(() =>
                      runWithCameraReadiness(handleStartSession),
                    )
                : () => void runWithVoiceReadiness(handleStartSession)
          }
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
            <div className="flex flex-col gap-4">
              {/* Mounted whenever the camera is opted in, not only while active — the hook needs
                  the element to exist before startVideo() can attach the stream. Mirrored for
                  comfort; the frames fed to MediaPipe are NOT mirrored. */}
              {cameraEnabled ? (
                <div className="relative self-center overflow-hidden rounded-xl border border-border bg-black">
                  <video
                    ref={videoRef}
                    muted
                    playsInline
                    className="h-[180px] w-[240px] -scale-x-100 object-cover"
                  />
                  {!isVideoActive ? (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/70 px-4 text-center text-xs text-white">
                      {isStartingVideo
                        ? `${videoStatus}${loadProgress !== null ? ` ${Math.round(loadProgress * 100)}%` : ""}`
                        : "Camera starts when you begin recording"}
                    </div>
                  ) : null}
                  {/* Live visual feedback, mirroring the calibration modal's framing banner but
                      terse — this competes with the transcript for attention during recording,
                      so it only appears when there's actually something to fix. */}
                  {liveVisualHint ? (
                    <div className="absolute inset-x-0 bottom-0 bg-warning/90 px-2 py-1 text-center text-[11px] font-medium text-white">
                      {liveVisualHint}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {videoError ? (
                <p className="text-center text-sm text-warning">{videoError}</p>
              ) : null}

              {/* Said here rather than only in the results, where it arrives too late to act on:
                  the camera looks identical whether or not eye contact will be scored, so
                  without this the first sign is a tile that declines to show a number. */}
              {isVideoActive && !gazeScorable ? (
                <p className="text-center text-sm text-muted-foreground">
                  Posture and gestures are being measured. Eye contact isn&apos;t — that needs the
                  camera calibration step, which was skipped or didn&apos;t take. Restart the
                  session to run it.
                </p>
              ) : null}

              <div className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-border p-6">
                <button
                  onClick={isVoiceActive ? handleStopVoice : () => void runWithVoiceReadiness(handleStartVoice)}
                  disabled={isConnectingVoice || isStoppingVoice}
                  className={cn(
                    "flex h-20 w-20 items-center justify-center rounded-full transition-all disabled:opacity-60",
                    isVoiceActive
                      ? "bg-danger text-white animate-pulse"
                      : "bg-primary text-white hover:scale-110",
                  )}
                >
                  <Mic className="h-10 w-10" />
                </button>
                <div className="text-center">
                  <div className="font-medium text-foreground">
                    {isConnectingVoice
                      ? "Connecting..."
                      : isVoiceActive
                        ? "Recording — tap to stop"
                        : "Tap to Record"}
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {voiceStatus || "We transcribe as you speak — review below before submitting."}
                  </div>
                </div>
              </div>

              {/* Speaking to a face beats speaking to a browser tab, but it is still a live
                  room — opt in, same as the Q&A call does. The avatar here is silent by
                  construction, so it cannot intrude on what is being recorded. */}
              {idleAudienceActive ? (
                <IdleAudiencePanel
                  sessionId={sessionId!}
                  active={idleAudienceActive}
                  onHide={() => setIdleAudienceActive(false)}
                />
              ) : (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIdleAudienceActive(true)}
                  className="w-full"
                >
                  Show an audience to speak to
                </Button>
              )}
              <Textarea
                label="Transcript (editable)"
                value={textContent}
                onChange={(e) => setTextContent(e.target.value)}
                placeholder="Your spoken words appear here..."
                rows={6}
              />
              {voiceError ? (
                <p className="text-sm text-danger">{voiceError}</p>
              ) : null}
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
            disabled={isSubmitting || isVoiceActive || !textContent.trim()}
            className="w-full"
          >
            {isSubmitting ? "Analyzing..." : "Submit for Analysis"}
          </Button>
        </div>
      ) : qaQuestion && showQa ? (
        !qaScore ? (
          <div className="flex flex-col gap-6 rounded-2xl border border-border bg-surface-elevated p-6">
            <div>
              <h2 className="font-semibold text-foreground">Audience Q&A</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                An audience member has a follow-up question. Respond impromptu.
              </p>
            </div>

            {qaCallActive ? (
              <QaAvatarCall
                sessionId={sessionId!}
                active={qaCallActive}
                question={qaQuestion}
                // The spoken answer fills the box below, so ending the call leaves the caller
                // ready to submit rather than retyping what they just said.
                onSelfSpeech={setQaResponse}
                onEnded={() => setQaCallActive(false)}
              />

            ) : (
              <>
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

                {/* Facing a person is most of what makes Q&A practice worth doing, but it is a
                    live call — opt in rather than opening a room the moment results render. */}
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setQaCallActive(true)}
                  className="w-full"
                >
                  Answer face-to-face instead
                </Button>
              </>
            )}

            <Textarea
              label={qaCallActive ? "Or type your response" : "Your response"}
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

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
        )
      ) : (
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

          {scorecard.video ? (
            <VideoPresenceSection video={scorecard.video} timeline={scorecard.video_timeline} />
          ) : null}

          {sessionId && <FillerWordsScorecardSection sessionId={sessionId} />}


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

          {qaQuestion ? (
            <Button onClick={() => setShowQa(true)} className="w-full">
              Continue to Audience Q&A
            </Button>
          ) : (
            <Button onClick={() => router.push("/dashboard/public-speaking")} className="w-full">
              Try Another Speech Type
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

/** Reason copy for a session the vision pipeline could not measure. Deliberately explains the
 *  capture problem rather than showing a low number — "8% eye contact" reads as a judgement,
 *  and users act on it even when the real answer is "the room was too dark". */
const VIDEO_REJECTION_COPY: Record<string, string> = {
  no_face_detected: "We couldn't see your face, so there's no delivery feedback this time.",
  face_coverage_too_low:
    "Your face was out of frame for much of the session, so delivery wasn't measured.",
  too_dark: "The room was too dark to analyse your delivery.",
  too_short: "The session was too short to measure delivery reliably.",
  framing_unusable: "The camera framing made delivery impossible to measure.",
  device_too_slow: "Your device couldn't keep up with the analysis, so delivery wasn't measured.",
  camera_stopped_early: "The camera stopped partway through, so delivery is incomplete.",
};

function VideoPresenceSection({
  video,
  timeline,
}: {
  video: NonNullable<PublicSpeakingScorecard["video"]>;
  timeline: PublicSpeakingScorecard["video_timeline"];
}) {
  if (video.rejection) {
    return (
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <div className="flex items-start gap-3">
          <Video className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
          <div>
            <div className="font-medium text-foreground">Delivery not measured</div>
            <p className="mt-1 text-sm text-muted-foreground">
              {VIDEO_REJECTION_COPY[video.rejection] ?? VIDEO_REJECTION_COPY.no_face_detected}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Without a good calibration the camera's position relative to the user's neutral head pose is
  // unknown, so every derived figure carries a large unmodelled bias — the backend reports that
  // as a very low confidence_weight. Showing "Eye Contact 62" off the back of that is precisely
  // the confident-wrong-number failure this feature is designed to avoid, so below this
  // threshold we confirm the capture worked and show nothing numeric.
  if (video.confidence_weight < 0.35) {
    return (
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <div className="flex items-start gap-3">
          <Video className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
          <div>
            <div className="font-medium text-foreground">Delivery captured</div>
            <p className="mt-1 text-sm text-muted-foreground">
              We analysed your body language on your device, but this session&apos;s camera
              calibration wasn&apos;t good enough to score it from — so we&apos;d rather show
              nothing than a misleading number. Run the calibration step at the start of your next
              session and hold still through the countdown. Nothing was uploaded.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const subScores: { label: string; value: number | null }[] = [
    { label: "Eye Contact", value: video.eye_contact },
    { label: "Posture", value: video.posture },
    { label: "Gestures", value: video.gestures },
    { label: "Expression", value: video.expression },
  ];

  return (
    <div className="rounded-lg border border-border bg-muted/30 p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Video className="h-5 w-5 text-primary" />
          <span className="font-medium text-foreground">Physical Delivery</span>
        </div>
        {video.visual_presence !== null ? (
          <span className="text-2xl font-bold text-foreground">
            {Math.round(video.visual_presence)}
          </span>
        ) : null}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {subScores.map(({ label, value }) => (
          <div key={label} className="rounded-lg bg-surface-elevated p-3 text-center">
            {/* An em dash, never a 0 — null means we couldn't measure it, and the two must not
                look the same to a reader. */}
            <div className="text-xl font-semibold text-foreground">
              {value === null ? "—" : Math.round(value)}
            </div>
            <div className="text-xs text-muted-foreground">{label}</div>
          </div>
        ))}
      </div>

      {timeline && timeline.length > 1 ? (
        <div className="mt-5 flex flex-col gap-4">
          {/* Only channels that were actually measured render — DeliverySparkline returns null
              when a channel has fewer than two real values, so a session without the pose model
              simply shows fewer charts rather than an empty axis. */}
          <DeliverySparkline
            label="Eye contact over time"
            values={timeline.eye_contact}
            binSeconds={timeline.bin_seconds}
          />
          <DeliverySparkline
            label="Posture over time"
            values={timeline.posture.map((v) => (v === null ? null : v / 100))}
            binSeconds={timeline.bin_seconds}
            className="stroke-success"
          />
          <DeliverySparkline
            label="Gesture activity"
            values={timeline.gesture_activity}
            binSeconds={timeline.bin_seconds}
            className="stroke-warning"
            format={(mean) => `${mean.toFixed(2)} avg`}
          />
        </div>
      ) : null}

      {/* Phase 1 ships without gaze calibration, so the eye-contact figure is provisional and
          says so. Removing this line requires the phase 2 calibration flow to exist. */}
      {video.confidence_weight < 0.7 ? (
        <p className="mt-3 text-xs text-muted-foreground">
          These delivery numbers are provisional — camera position varies between setups, so
          treat them as a rough guide rather than an exact measurement.
        </p>
      ) : null}
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