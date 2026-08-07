"use client";

/**
 * The pieces shared by the two rooms Public Speaking opens: the Q&A call (QaAvatarCall) and the
 * silent audience shown during the speech itself (IdleAudiencePanel). Only the framing differs
 * — the video panel, its placeholder states, and the LiveKit room wiring are the same.
 */

import * as React from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  VideoTrack,
  useTracks,
  useVoiceAssistant,
} from "@livekit/components-react";
import { Track } from "livekit-client";
import { Loader2 } from "lucide-react";

import type { LiveCallConnection } from "@/lib/useLiveCallConnection";

/** Generous enough for a cold worker subprocess plus the avatar provider's own handshake, which
 *  together ran ~13s in practice. Past this the agent is not coming. */
const AGENT_JOIN_TIMEOUT_MS = 25_000;

export function Panel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="relative aspect-video overflow-hidden rounded-xl border border-border bg-black">
        {children}
      </div>
    </div>
  );
}

export function PanelPlaceholder({ text, spinner }: { text: string; spinner?: boolean }) {
  return (
    <div className="flex h-full w-full items-center justify-center gap-2 px-4 text-center text-xs text-white/80">
      {spinner ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
      {text}
    </div>
  );
}

/** Renders the agent's published video track, with its speaking state as the fallback caption.
 *
 *  useVoiceAssistant identifies the agent from its participant attributes, which the idle
 *  audience — an AgentSession with no STT/LLM/TTS — does not necessarily advertise the same way
 *  a conversational one does. So fall back to the first remote camera track in the room: for
 *  these two rooms the only other publisher is the avatar. */
export function AvatarVideo({ idleCaption }: { idleCaption?: string }) {
  const { videoTrack, state } = useVoiceAssistant();
  const cameraTracks = useTracks([Track.Source.Camera], { onlySubscribed: true });
  const remoteTrack = cameraTracks.find((track) => !track.participant.isLocal);
  const track = videoTrack ?? remoteTrack;

  // An agent that never joins is invisible to onError: the room connected fine, it is simply
  // empty, so without this the panel waits forever. Every reason it fails to arrive — worker
  // not running, avatar credentials rejected, job crashed on startup — looks identical here.
  const [joinTimedOut, setJoinTimedOut] = React.useState(false);
  React.useEffect(() => {
    if (track) return;
    const timer = setTimeout(() => setJoinTimedOut(true), AGENT_JOIN_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [track]);

  if (track) {
    return <VideoTrack trackRef={track} className="h-full w-full object-cover" />;
  }

  if (joinTimedOut) {
    return <PanelPlaceholder text="The audience didn't join. Check the agent worker's logs." />;
  }

  // Beyond Presence is env-gated in live_call/worker.py: with no BEY_API_KEY the call runs
  // audio-only and no video track ever arrives. That is a supported mode, not a failure, so
  // show the agent's state rather than an error.
  if (idleCaption) return <PanelPlaceholder text={idleCaption} spinner />;
  return (
    <PanelPlaceholder
      text={state === "speaking" ? "Speaking…" : state === "thinking" ? "Thinking…" : "Listening…"}
    />
  );
}

interface AvatarRoomProps {
  connection: LiveCallConnection | null;
  connecting: boolean;
  /** From useLiveCallConnection — covers the token request only. */
  tokenError: string | null;
  /** Shown for any failure, whether it came from the token request or the room itself. */
  errorText: string;
  /** Publish the local mic. False for the idle audience: nothing in that room listens, and the
   *  speech phase's own recorder already holds the microphone. */
  publishAudio?: boolean;
  onDisconnected: () => void;
  children: React.ReactNode;
}

/** The room itself, plus the states that stand in for it.
 *
 *  Everything after a successful token — connect, publish, a worker that never joins — used to
 *  fail with nothing on screen and nothing in the console. onError/onMediaDeviceFailure are the
 *  only place those surface. */
export function AvatarRoom({
  connection,
  connecting,
  tokenError,
  errorText,
  publishAudio = true,
  onDisconnected,
  children,
}: AvatarRoomProps) {
  const [roomError, setRoomError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!connection) setRoomError(null);
  }, [connection]);

  if (tokenError || roomError) return <PanelPlaceholder text={errorText} />;

  if (!connection) {
    return <PanelPlaceholder text={connecting ? "Connecting…" : "Starting…"} spinner />;
  }

  return (
    <LiveKitRoom
      serverUrl={connection.url}
      token={connection.token}
      connect
      audio={publishAudio}
      video={false}
      onDisconnected={onDisconnected}
      onError={(err) => {
        console.error("[live-call] room error:", err);
        setRoomError(err.message);
      }}
      onMediaDeviceFailure={(failure, kind) => {
        console.error("[live-call] media device failure:", failure, kind);
        setRoomError(`${kind ?? "media"} unavailable: ${failure ?? "unknown"}`);
      }}
      className="h-full w-full"
    >
      <RoomAudioRenderer />
      {children}
    </LiveKitRoom>
  );
}
