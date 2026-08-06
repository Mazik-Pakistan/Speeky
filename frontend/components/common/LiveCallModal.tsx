"use client";

import * as React from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  useLocalParticipant,
  useMultibandTrackVolume,
  useTranscriptions,
  type TrackReference,
} from "@livekit/components-react";
import type { LocalAudioTrack } from "livekit-client";
import { Mic, MicOff, PhoneOff, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { fetchLiveCallToken, type LiveCallFeature } from "@/lib/liveCall";
import { stopCurrent } from "@/lib/tts";

const STATE_LABELS: Record<string, string> = {
  connecting: "Connecting…",
  initializing: "Connecting…",
  listening: "Listening…",
  thinking: "Thinking…",
  speaking: "Speaking…",
  disconnected: "Disconnected",
};

const ORB_BANDS = 4;

interface LiveCallModalProps {
  feature: LiveCallFeature;
  sessionId: string;
  open: boolean;
  onClose: () => void;
  /** "End Session" — finalize + show the feature's normal feedback report. */
  onEndSession: () => void | Promise<void>;
  /** "End Call" — just hang up; the call's turns already persisted into the
   * session's normal history as they happened, so the user can keep going by
   * text/push-to-talk with full context. */
  onCallEnded?: () => void;
}

/**
 * Shared Live Call UI for Conversation / Interview Coach / Scenario. Renders
 * as a full-screen sheet on small viewports and a centered card on larger
 * ones. Background + orb are a CSS-only ambient visualization (no WebGL/
 * third-party shader) built from the app's own --primary/--accent theme
 * tokens, so it's themed automatically in both light and dark mode.
 */
export function LiveCallModal({
  feature,
  sessionId,
  open,
  onClose,
  onEndSession,
  onCallEnded,
}: LiveCallModalProps) {
  const [connection, setConnection] = React.useState<{ token: string; url: string } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [connecting, setConnecting] = React.useState(false);
  const [endingSession, setEndingSession] = React.useState(false);

  React.useEffect(() => {
    if (!open) {
      setConnection(null);
      setError(null);
      return;
    }
    // The chat page's "Audio mode" TTS (lib/tts.ts) may still be reading out a
    // previous message when Live Call opens — without this they talk over each
    // other. Live Call owns the mic/speaker from here on.
    stopCurrent();
    let cancelled = false;
    setConnecting(true);
    setError(null);
    fetchLiveCallToken(feature, sessionId)
      .then((result) => {
        if (!cancelled) setConnection({ token: result.token, url: result.url });
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Couldn't start the call.");
        }
      })
      .finally(() => {
        if (!cancelled) setConnecting(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, feature, sessionId]);

  if (!open) return null;

  async function handleEndSession() {
    setEndingSession(true);
    try {
      await onEndSession();
    } finally {
      setEndingSession(false);
      setConnection(null);
      onClose();
    }
  }

  function handleEndCall() {
    setConnection(null);
    onClose();
    onCallEnded?.();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-sm sm:items-center sm:p-4">
      {/* h-auto + max-h-[Xvh] (not a fixed h-[Xvh]) above mobile — the card sizes to
          its actual content and only clamps (letting the captions region scroll
          internally) on a viewport short enough that content genuinely doesn't
          fit. A fixed vh height clipped the button row off the bottom edge on
          real desktop windows shorter than assumed (browser chrome, OS scaling,
          a non-maximized window). */}
      <div className="flex h-[100dvh] max-h-[100dvh] w-full min-h-0 flex-col overflow-hidden bg-[radial-gradient(ellipse_at_50%_10%,hsl(var(--primary)/0.28),hsl(var(--background))_65%)] sm:h-auto sm:max-h-[85vh] sm:w-[90vw] sm:max-w-md sm:rounded-2xl sm:border sm:border-border sm:shadow-xl md:w-3/5 md:max-w-2xl md:max-h-[80vh] lg:w-1/2 lg:max-w-3xl lg:max-h-[75vh]">
        <div className="flex shrink-0 items-center justify-between px-4 py-3 sm:px-5">
          <p className="text-sm font-semibold text-foreground">Live Call</p>
          <button
            type="button"
            onClick={handleEndCall}
            aria-label="Close"
            className="rounded-lg p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {error ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
            <p className="text-sm text-danger">{error}</p>
            <Button size="sm" variant="outline" onClick={onClose}>
              Close
            </Button>
          </div>
        ) : connecting || !connection ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6">
            <span
              className="h-8 w-8 animate-spin rounded-full border-2 border-current border-t-transparent text-muted-foreground"
              aria-hidden="true"
            />
            <p className="text-sm text-muted-foreground">Connecting…</p>
          </div>
        ) : (
          <LiveKitRoom
            token={connection.token}
            serverUrl={connection.url}
            connect
            audio
            video={false}
            className="flex min-h-0 flex-1 flex-col overflow-hidden"
            onDisconnected={() => setConnection(null)}
          >
            <RoomAudioRenderer />
            <LiveCallControls
              endingSession={endingSession}
              onEndSession={() => void handleEndSession()}
              onEndCall={handleEndCall}
            />
          </LiveKitRoom>
        )}
      </div>
    </div>
  );
}

function LiveCallControls({
  endingSession,
  onEndSession,
  onEndCall,
}: {
  endingSession: boolean;
  onEndSession: () => void;
  onEndCall: () => void;
}) {
  const { state, audioTrack } = useVoiceAssistant();
  const { localParticipant, isMicrophoneEnabled, microphoneTrack } = useLocalParticipant();

  return (
    <div className="flex min-h-0 flex-1 flex-col p-4 sm:p-6">
      {/* Orb + status never scroll or shrink — always fully visible no matter how
          long the caption text below grows or how much vertical room the modal has. */}
      <div className="flex shrink-0 flex-col items-center gap-3 pt-2">
        <LiveCallOrb
          state={state}
          agentAudioTrack={audioTrack}
          localMicTrack={microphoneTrack?.track as LocalAudioTrack | undefined}
        />
        <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
          {STATE_LABELS[state] ?? "Connected"}
        </p>
      </div>

      {/* Captions — the only part allowed to scroll. A long exchange gets its own
          scrollbar here instead of dragging the orb along with it or growing the
          modal past its bounds; short exchanges (the common case) just sit centered
          in the space below the orb, no scrollbar at all since nothing overflows. */}
      <div className="mt-3 flex min-h-0 flex-1 flex-col items-center justify-center overflow-y-auto">
        <LiveCallLastLines localIdentity={localParticipant.identity} />
      </div>

      <div className="flex shrink-0 flex-col items-center gap-3 pt-3">
        <div className="flex items-center gap-5">
          <button
            type="button"
            onClick={() => void localParticipant.setMicrophoneEnabled(!isMicrophoneEnabled)}
            aria-pressed={isMicrophoneEnabled}
            aria-label={isMicrophoneEnabled ? "Mute microphone" : "Unmute microphone"}
            className={cn(
              "flex h-12 w-12 shrink-0 items-center justify-center rounded-full border transition-colors sm:h-14 sm:w-14",
              isMicrophoneEnabled
                ? "border-border bg-surface text-foreground hover:bg-muted"
                : "border-danger bg-danger/10 text-danger",
            )}
          >
            {isMicrophoneEnabled ? (
              <Mic className="h-5 w-5" aria-hidden="true" />
            ) : (
              <MicOff className="h-5 w-5" aria-hidden="true" />
            )}
          </button>
          <button
            type="button"
            onClick={onEndCall}
            aria-label="End call — keep chatting by text"
            title="End call — keep chatting by text"
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-danger text-white shadow-sm transition-colors hover:bg-danger/90 sm:h-14 sm:w-14"
          >
            <PhoneOff className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        <Button
          size="sm"
          variant="outline"
          loading={endingSession}
          onClick={onEndSession}
          className="w-full sm:w-auto"
        >
          End Session &amp; See Report
        </Button>
      </div>
    </div>
  );
}

/**
 * Multi-band-reactive ambient orb — swaps between --accent (you're talking)
 * and --primary (agent talking); each of the 4 concentric layers is bound to
 * a different frequency band (low band on the outer glow, high band on the
 * core), so it visibly reshapes with pitch/timbre, not just loudness. Pure
 * CSS transforms off real Web Audio frequency data (useMultibandTrackVolume)
 * — no canvas, no WebGL, no third-party shader.
 */
function LiveCallOrb({
  state,
  agentAudioTrack,
  localMicTrack,
}: {
  state: string;
  agentAudioTrack?: TrackReference;
  localMicTrack?: LocalAudioTrack;
}) {
  const isAgentTurn = state === "speaking" || state === "thinking";
  const activeTrack = isAgentTurn ? agentAudioTrack : localMicTrack;
  const rawBands = useMultibandTrackVolume(activeTrack, { bands: ORB_BANDS, updateInterval: 50 });
  const [bass, low, high, treble] =
    rawBands.length === ORB_BANDS ? rawBands.map((v) => Math.min(v, 1)) : [0, 0, 0, 0];

  const colorClass = isAgentTurn ? "bg-primary" : "bg-accent";
  const colorVar = isAgentTurn ? "--primary" : "--accent";

  return (
    <div className="relative flex h-28 w-28 shrink-0 items-center justify-center sm:h-44 sm:w-44 md:h-52 md:w-52">
      {/* Bass — outermost, softest, widest swing */}
      <div
        className={cn("absolute inset-0 rounded-full blur-3xl transition-[background-color] duration-700 ease-out", colorClass)}
        style={{ opacity: 0.28 + bass * 0.5, transform: `scale(${0.85 + bass * 0.45})` }}
      />
      {/* Low-mid */}
      <div
        className={cn("absolute h-4/5 w-4/5 rounded-full blur-2xl transition-[background-color] duration-500 ease-out", colorClass)}
        style={{ opacity: 0.32 + low * 0.45, transform: `scale(${0.88 + low * 0.32})` }}
      />
      {/* High-mid */}
      <div
        className={cn("absolute h-3/5 w-3/5 rounded-full blur-xl transition-[background-color] duration-500 ease-out", colorClass)}
        style={{ opacity: 0.4 + high * 0.4, transform: `scale(${0.9 + high * 0.22})` }}
      />
      {/* Treble — core, sharpest response, real glow via box-shadow */}
      <div
        className={cn("relative h-2/5 w-2/5 rounded-full transition-[background-color] duration-700 ease-out", colorClass)}
        style={{
          transform: `scale(${0.94 + treble * 0.22})`,
          boxShadow: `0 0 ${30 + treble * 40}px ${6 + treble * 12}px hsl(var(${colorVar}) / ${0.35 + treble * 0.4})`,
        }}
      />
    </div>
  );
}

type TranscriptSegment = ReturnType<typeof useTranscriptions>[number];

/** Tracks a hand-off between two values keyed by id: the outgoing one stays
 * mounted just long enough to play its fade-out-up exit, then drops. */
function useFadeHandoff(value: TranscriptSegment | null) {
  const [{ current, exiting }, setPair] = React.useState<{
    current: TranscriptSegment | null;
    exiting: TranscriptSegment | null;
  }>({ current: value, exiting: null });
  const idRef = React.useRef(value?.streamInfo.id ?? null);

  React.useEffect(() => {
    const nextId = value?.streamInfo.id ?? null;
    if (nextId === idRef.current) {
      // Same segment, just more text streamed in (LiveKit paces long agent replies
      // out word-by-word under one stream id) — update in place, no fade handoff.
      // Without this branch `current` freezes on whatever text existed at the first
      // render for this id, which is why only the first word or two ever showed.
      setPair((prev) => ({ ...prev, current: value }));
      return;
    }
    idRef.current = nextId;
    setPair((prev) => ({ current: value, exiting: prev.current }));
    const timer = setTimeout(() => setPair((prev) => ({ ...prev, exiting: null })), 320);
    return () => clearTimeout(timer);
  }, [value]);

  return { current, exiting };
}

function FadingLine({
  segment,
  label,
  className,
}: {
  segment: TranscriptSegment;
  label: string;
  className?: string;
}) {
  return (
    <p className={cn("text-sm", className)}>
      <span className="mr-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {segment.text}
    </p>
  );
}

/** One speaker's slot: exiting line (fading/drifting up, absolutely
 * positioned so it doesn't push layout) behind the incoming line (fading up
 * into its normal position) — a real hand-off, not an instant swap. */
function LiveCallSpeakerSlot({
  segment,
  label,
  className,
}: {
  segment: TranscriptSegment | null;
  label: string;
  className?: string;
}) {
  const { current, exiting } = useFadeHandoff(segment);
  if (!current && !exiting) return null;

  return (
    <div className="relative w-full">
      {exiting ? (
        <div className="pointer-events-none absolute inset-x-0 bottom-full">
          <FadingLine
            key={exiting.streamInfo.id}
            segment={exiting}
            label={label}
            className={cn("animate-fade-out-up", className)}
          />
        </div>
      ) : null}
      {current ? (
        <FadingLine
          key={current.streamInfo.id}
          segment={current}
          label={label}
          className={cn("animate-fade-up", className)}
        />
      ) : null}
    </div>
  );
}

/**
 * Just the most recent AI line and most recent your-line — not a transcript,
 * not a chat log. Each is replaced (with a fade-out/fade-in hand-off, not an
 * instant swap) when a newer one for that speaker arrives.
 */
function LiveCallLastLines({ localIdentity }: { localIdentity: string }) {
  const transcriptions = useTranscriptions();

  const latestFor = (matchLocal: boolean) => {
    let latest: TranscriptSegment | null = null;
    for (const seg of transcriptions) {
      const isLocal = seg.participantInfo.identity === localIdentity;
      if (isLocal !== matchLocal) continue;
      if (!latest || seg.streamInfo.timestamp > latest.streamInfo.timestamp) latest = seg;
    }
    return latest;
  };

  const latestAgent = latestFor(false);
  const latestUser = latestFor(true);

  if (!latestAgent && !latestUser) return null;

  return (
    <div className="flex w-full max-w-sm flex-col items-center gap-1.5 text-center sm:max-w-md md:max-w-xl lg:max-w-2xl">
      <LiveCallSpeakerSlot segment={latestAgent} label="Coach" className="text-foreground" />
      <LiveCallSpeakerSlot segment={latestUser} label="You" className="text-muted-foreground" />
    </div>
  );
}
