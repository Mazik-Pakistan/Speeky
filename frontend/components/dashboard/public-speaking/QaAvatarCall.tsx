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

import {
  AvatarRoom,
  AvatarVideo,
  CallTranscript,
  Panel,
  PanelPlaceholder,
} from "./AvatarVideoPanel";

/** Speaker on the left, audience on the right, transcript spanning underneath. The room's own
 *  children slot straight in as grid items — see AvatarRoom's className. */
function Layout({ selfView, children }: { selfView: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <Panel label="You">{selfView}</Panel>
      {children}
    </div>
  );
}

interface QaAvatarCallProps {
  sessionId: string;
  /** The session must already be in qa_phase; the token request fails otherwise. */
  active: boolean;
  /** The question the avatar speaks on connect (dispatch.py passes it as the opening line).
   *  Kept collapsed here as a fallback for a user who mishears it or has the volume down —
   *  reading it before the avatar has said it would give the answer away. */
  question: string | null;
  /** The caller's own speech, transcribed, for the answer box below. Replaces rather than
   *  appends — see CallTranscript. */
  onSelfSpeech?: (text: string) => void;
  onEnded: () => void;
}

export function QaAvatarCall({
  sessionId,
  active,
  question,
  onSelfSpeech,
  onEnded,
}: QaAvatarCallProps) {
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
        <details className="rounded-lg bg-muted/50 px-3 py-2">
          <summary className="cursor-pointer text-sm text-muted-foreground marker:text-muted-foreground">
            Missed the question?
          </summary>
          <p className="mt-2 text-sm text-foreground">&ldquo;{question}&rdquo;</p>
        </details>
      ) : null}

      {/* The self-view is deliberately outside the room: it is a plain local capture, so it
          should stay on screen while the room connects, and survive the room failing entirely. */}
      <Layout
        selfView={
          cameraError ? (
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
          )
        }
      >
        {/* Losing the avatar must not lose the Q&A — the answer is still typed and scored the
            normal way, so this degrades to the existing text flow rather than blocking. */}
        <AvatarRoom
          connection={connection}
          connecting={connecting}
          tokenError={error}
          errorText="Couldn't reach the audience — answer below instead."
          onDisconnected={onEnded}
          placeholderWrapper={(placeholder) => <Panel label="Audience">{placeholder}</Panel>}
          className="contents"
        >
          <Panel label="Audience">
            <AvatarVideo />
          </Panel>
          <CallTranscript onSelfSpeech={onSelfSpeech} />
        </AvatarRoom>
      </Layout>
    </div>
  );
}
