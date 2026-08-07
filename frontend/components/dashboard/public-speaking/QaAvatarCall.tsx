"use client";

/**
 * Side-by-side Q&A call: the speaker on the left, the avatar audience member on the right.
 *
 * Only rendered once the session reaches `qa_phase`. During the speech itself there is no
 * talking agent — one would talk over a monologue, and its voice would be picked up by the mic
 * feeding the audio scorer (`useVoiceSocket` captures with no echo cancellation). The backend
 * enforces this too: `live_call_service` refuses to mint a "qa" token before `qa_phase`. The
 * silent audience shown during the speech is a separate mode — see IdleAudiencePanel.
 *
 * The self-view is its own capture, not the speech phase's MediaPipe stream: that camera is
 * released the moment recording stops, and its <video> element unmounts with the recording
 * screen. Q&A is not scored, so there is nothing to share between them anyway.
 */

import * as React from "react";
import { PhoneOff, Video as VideoIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useLiveCallConnection } from "@/lib/useLiveCallConnection";
import { useSelfCamera } from "@/lib/useSelfCamera";

import { AvatarRoom, AvatarVideo, Panel, PanelPlaceholder } from "./AvatarVideoPanel";

interface QaAvatarCallProps {
  sessionId: string;
  /** The session must already be in qa_phase; the token request fails otherwise. */
  active: boolean;
  /** The question, shown as text alongside the spoken version — a user who mishears or has the
   *  volume down should never be stuck. */
  question: string | null;
  onEnded: () => void;
}

export function QaAvatarCall({ sessionId, active, question, onEnded }: QaAvatarCallProps) {
  const { connection, connecting, error, disconnect } = useLiveCallConnection(
    "public_speaking",
    sessionId,
    active,
  );
  const { videoRef, error: cameraError } = useSelfCamera(active);

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
        <Panel label="You">
          {cameraError ? (
            <PanelPlaceholder text={cameraError} />
          ) : (
            // Mirrored, matching the recording screen's self-view — an unmirrored view of
            // yourself reads as wrong even though it is what the audience sees.
            <video
              ref={videoRef}
              muted
              playsInline
              className="h-full w-full -scale-x-100 object-cover"
            />
          )}
        </Panel>

        <Panel label="Audience">
          {/* Losing the avatar must not lose the Q&A — the answer is still typed and scored the
              normal way, so this degrades to the existing text flow rather than blocking. */}
          <AvatarRoom
            connection={connection}
            connecting={connecting}
            tokenError={error}
            errorText="Couldn't reach the audience — answer below instead."
            onDisconnected={onEnded}
          >
            <AvatarVideo />
          </AvatarRoom>
        </Panel>
      </div>
    </div>
  );
}
