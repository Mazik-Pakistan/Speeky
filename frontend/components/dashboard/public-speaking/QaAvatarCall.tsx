"use client";

/**
 * Side-by-side Q&A call: the speaker on the left, the avatar audience member on the right.
 *
 * Only rendered once the session reaches `qa_phase`. During the speech itself there is no room
 * and no avatar — a live participant would talk over a monologue, and its voice would be picked
 * up by the mic feeding the audio scorer (`useVoiceSocket` captures with no echo cancellation).
 * The backend enforces this too: `live_call_service` refuses to mint a token before `qa_phase`.
 *
 * The user's own webcam panel deliberately reuses whatever `<video>` the caller already has
 * running for MediaPipe rather than opening a second capture — one camera, one stream.
 */

import * as React from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  VideoTrack,
  useVoiceAssistant,
} from "@livekit/components-react";
import { Loader2, PhoneOff, Video as VideoIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useLiveCallConnection } from "@/lib/useLiveCallConnection";

interface QaAvatarCallProps {
  sessionId: string;
  /** The session must already be in qa_phase; the token request fails otherwise. */
  active: boolean;
  /** The question, shown as text alongside the spoken version — a user who mishears or has the
   *  volume down should never be stuck. */
  question: string | null;
  /** Rendered into the left panel: the existing self-view, not a second camera. */
  selfView?: React.ReactNode;
  onEnded: () => void;
}

export function QaAvatarCall({
  sessionId,
  active,
  question,
  selfView,
  onEnded,
}: QaAvatarCallProps) {
  const { connection, connecting, error, disconnect } = useLiveCallConnection(
    "public_speaking",
    sessionId,
    active,
  );

  function handleEnd() {
    disconnect();
    onEnded();
  }

  if (!active) return null;

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface-elevated p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <VideoIcon className="h-5 w-5 text-primary" />
          <span className="font-medium text-foreground">Audience Q&amp;A</span>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={handleEnd}>
          <PhoneOff className="mr-2 h-4 w-4" />
          End Q&amp;A
        </Button>
      </div>

      {question ? (
        <p className="rounded-lg bg-muted/50 px-3 py-2 text-sm text-foreground">
          &ldquo;{question}&rdquo;
        </p>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        <Panel label="You">{selfView ?? <PanelPlaceholder text="Camera off" />}</Panel>

        <Panel label="Audience">
          {error ? (
            // Losing the avatar must not lose the Q&A — the answer is still typed and scored the
            // normal way, so this degrades to the existing text flow rather than blocking.
            <PanelPlaceholder text="Couldn't reach the audience — answer below instead." />
          ) : connection ? (
            <LiveKitRoom
              serverUrl={connection.url}
              token={connection.token}
              connect
              audio
              video={false}
              onDisconnected={onEnded}
              className="h-full w-full"
            >
              <RoomAudioRenderer />
              <AvatarVideo />
            </LiveKitRoom>
          ) : (
            <PanelPlaceholder
              text={connecting ? "Connecting…" : "Starting…"}
              spinner
            />
          )}
        </Panel>
      </div>
    </div>
  );
}

/** Renders the agent's published video track, or its speaking state while it has none. */
function AvatarVideo() {
  const { videoTrack, state } = useVoiceAssistant();

  if (videoTrack) {
    return <VideoTrack trackRef={videoTrack} className="h-full w-full object-cover" />;
  }

  // Beyond Presence is env-gated in live_call/worker.py: with no BEY_API_KEY the call runs
  // audio-only and no video track ever arrives. That is a supported mode, not a failure, so
  // show the agent's state rather than an error.
  return (
    <PanelPlaceholder
      text={state === "speaking" ? "Speaking…" : state === "thinking" ? "Thinking…" : "Listening…"}
    />
  );
}

function Panel({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="relative aspect-video overflow-hidden rounded-xl border border-border bg-black">
        {children}
      </div>
    </div>
  );
}

function PanelPlaceholder({ text, spinner }: { text: string; spinner?: boolean }) {
  return (
    <div
      className={cn(
        "flex h-full w-full items-center justify-center gap-2 px-4 text-center text-xs text-white/80",
      )}
    >
      {spinner ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
      {text}
    </div>
  );
}
