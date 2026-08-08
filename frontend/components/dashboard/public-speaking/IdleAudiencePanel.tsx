"use client";

/**
 * A silent audience member to deliver the speech to, shown during the speech phase itself.
 *
 * The avatar here never speaks and never listens: the backend starts it with no STT, LLM or TTS
 * at all (live_call/worker.py `_run_idle_audience`), which is what makes it safe to have in the
 * room while the mic is recording audio that gets scored. It is presence, not conversation —
 * the talking avatar belongs to the Q&A phase (QaAvatarCall) and is gated separately.
 *
 * Hiding it must never touch session state: this is decoration on top of a recording in
 * progress, so there is no onEnded and nothing to submit.
 */

import * as React from "react";
import { EyeOff, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useLiveCallConnection } from "@/lib/useLiveCallConnection";

import { AvatarRoom, AvatarVideo, Panel } from "./AvatarVideoPanel";

interface IdleAudiencePanelProps {
  sessionId: string;
  /** The session must still be in_progress; the token request fails otherwise. */
  active: boolean;
  onHide: () => void;
}

export function IdleAudiencePanel({ sessionId, active, onHide }: IdleAudiencePanelProps) {
  const { connection, connecting, error, disconnect } = useLiveCallConnection(
    "public_speaking",
    sessionId,
    active,
    "idle",
  );

  function handleHide() {
    disconnect();
    onHide();
  }

  if (!active) return null;

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-border bg-surface-elevated p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Users className="h-5 w-5 text-primary" />
          <span className="font-medium text-foreground">Your audience</span>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={handleHide}>
          <EyeOff className="mr-2 h-4 w-4" />
          Hide audience
        </Button>
      </div>

      <div className="mx-auto w-full max-w-md">
        <Panel label="Listening">
          {/* Failing here costs the user nothing — the speech records and scores exactly the
              same with an empty panel, so this stays a caption rather than an error. */}
          <AvatarRoom
            connection={connection}
            connecting={connecting}
            tokenError={error}
            errorText="No audience available right now — carry on, your speech still records."
            publishAudio={false}
            onDisconnected={onHide}
          >
            <AvatarVideo idleCaption="Waiting for your audience…" />
          </AvatarRoom>
        </Panel>
      </div>
    </div>
  );
}
