"use client";

import { Trophy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import type { Milestone } from "@/lib/practiceTime";

interface MilestoneCelebrationModalProps {
  milestone: Milestone | null;
  onClose: () => void;
}

/** PDG-US-15: full-screen celebration when a practice-time milestone unlocks. */
export function MilestoneCelebrationModal({ milestone, onClose }: MilestoneCelebrationModalProps) {
  return (
    <Modal open={milestone !== null} onClose={onClose} title="Milestone Unlocked!">
      {milestone ? (
        <div className="flex flex-col items-center gap-4 py-2 text-center">
          <span className="flex h-16 w-16 items-center justify-center rounded-full bg-accent/15 text-accent">
            <Trophy className="h-8 w-8" aria-hidden="true" />
          </span>
          <p className="font-serif text-xl font-semibold text-foreground">{milestone.message}</p>
          <p className="text-sm text-muted-foreground">
            Your new badge has been added to your Progress Dashboard's Trophy Case.
          </p>
          <Button type="button" size="sm" onClick={onClose}>
            Keep Going
          </Button>
        </div>
      ) : null}
    </Modal>
  );
}
