"use client";

import * as React from "react";
import { AlertTriangle, Lock, Mic, Minus, TrendingDown, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { api, ApiError } from "@/lib/api";
import {
  getAccentProgressMatrix,
  type AccentProgressMatrix,
  type AccentTrend,
} from "@/lib/accentProgress";
import { cn } from "@/lib/utils";
import { AccentCheckInModal } from "./AccentCheckInModal";
import { MicrophoneCheckModal } from "./MicrophoneCheckModal";

const VOICE_CONSENT_POLICY_VERSION = "ACC-US-02-v1";

interface VoiceConsentStatus {
  granted: boolean;
}

function getVoiceConsent() {
  return api<VoiceConsentStatus>("/voice-consent");
}

function updateVoiceConsent(granted: boolean) {
  return api<VoiceConsentStatus>("/voice-consent", {
    method: "PATCH",
    body: JSON.stringify({
      granted,
      policy_version: VOICE_CONSENT_POLICY_VERSION,
    }),
  });
}

const TREND_STYLES: Record<
  AccentTrend,
  { rowClass: string; icon: typeof TrendingUp; iconClass: string }
> = {
  improved: { rowClass: "bg-success/10", icon: TrendingUp, iconClass: "text-success" },
  stagnated: { rowClass: "bg-muted/40", icon: Minus, iconClass: "text-muted-foreground" },
  degraded: { rowClass: "bg-danger/10", icon: TrendingDown, iconClass: "text-danger" },
};

interface VoiceConsentDisclosureModalProps {
  open: boolean;
  onClose: () => void;
  onAccepted: () => void;
}

function VoiceConsentDisclosureModal({
  open,
  onClose,
  onAccepted,
}: VoiceConsentDisclosureModalProps) {
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleAgree() {
    setError(null);
    setIsSubmitting(true);

    try {
      await updateVoiceConsent(true);
      onAccepted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save voice consent.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={isSubmitting ? () => {} : onClose}
      title="Voice Data Consent"
      description="Please review this before starting Accent Assessment."
    >
      <div className="flex flex-col gap-4 text-sm text-muted-foreground">
        <p>
          Speeky will use your microphone recording to assess pronunciation, stress,
          rhythm, intonation, and clarity.
        </p>

        <p>
          Your recording is sent to Speeky for AI scoring and accent profile generation.
          In this MVP, raw voice recordings are not retained after scoring.
        </p>

        <p>
          Your derived text-based scores and accent profile are kept so you can track
          progress. You can withdraw consent or delete stored voice samples from Profile
          settings at any time.
        </p>

        {error ? <p className="text-danger">{error}</p> : null}

        <div className="flex flex-wrap gap-3">
          <Button type="button" loading={isSubmitting} onClick={handleAgree}>
            I Agree
          </Button>
          <Button type="button" variant="outline" disabled={isSubmitting} onClick={onClose}>
            Not Now
          </Button>
          <Button href="/dashboard/explore" variant="ghost">
            Use Non-Voice Modules
          </Button>
        </div>
      </div>
    </Modal>
  );
}

/** ACC-US-15: Accent Progress Tracker - Month-Over-Month Matrix Visualization. */
export function AccentProgressTracker() {
  const [matrix, setMatrix] = React.useState<AccentProgressMatrix | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isCheckInOpen, setIsCheckInOpen] = React.useState(false);
  const [isConsentOpen, setIsConsentOpen] = React.useState(false);
  const [isMicCheckOpen, setIsMicCheckOpen] = React.useState(false);
  const [isCheckingConsent, setIsCheckingConsent] = React.useState(false);

  const loadMatrix = React.useCallback(() => {
    setIsLoading(true);
    getAccentProgressMatrix()
      .then(setMatrix)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong."))
      .finally(() => setIsLoading(false));
  }, []);

  React.useEffect(() => {
    loadMatrix();
  }, [loadMatrix]);

  async function handleStartAccentAssessment() {
    setError(null);
    setIsCheckingConsent(true);

    try {
      const consent = await getVoiceConsent();

      if (consent.granted) {
        setIsMicCheckOpen(true);
      } else {
        setIsConsentOpen(true);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not check voice consent.");
    } finally {
      setIsCheckingConsent(false);
    }
  }

  function handleCheckInSuccess() {
    setIsCheckInOpen(false);
    loadMatrix();
  }

  function handleConsentAccepted() {
    setIsConsentOpen(false);
    setIsMicCheckOpen(true);
  }

  function handleMicCheckPassed() {
    setIsMicCheckOpen(false);
    setIsCheckInOpen(true);
  }

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
        <p className="text-sm text-muted-foreground">Loading your accent progress...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
        <p className="text-sm text-danger">{error}</p>
      </div>
    );
  }

  if (!matrix) return null;

  if (matrix.force_baseline) {
    return (
      <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
        <h2 className="font-serif text-xl font-semibold text-foreground">Accent Progress Tracker</h2>

        <div className="mt-6 flex flex-col items-center gap-3 rounded-xl border border-dashed border-border p-8 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-secondary text-primary">
            <Mic className="h-5 w-5" aria-hidden="true" />
          </span>
          <p className="max-w-sm text-sm text-muted-foreground">{matrix.message}</p>
          <Button
            type="button"
            size="sm"
            loading={isCheckingConsent}
            onClick={handleStartAccentAssessment}
          >
            Complete Baseline Accent Assessment
          </Button>
        </div>

        <AccentCheckInModal
          open={isCheckInOpen}
          onClose={() => setIsCheckInOpen(false)}
          onSuccess={handleCheckInSuccess}
        />

        <VoiceConsentDisclosureModal
          open={isConsentOpen}
          onClose={() => setIsConsentOpen(false)}
          onAccepted={handleConsentAccepted}
        />

        <MicrophoneCheckModal
          open={isMicCheckOpen}
          onClose={() => setIsMicCheckOpen(false)}
          onPassed={handleMicCheckPassed}
        />
      </div>
    );
  }

  const metrics = matrix.metrics ?? [];

  return (
    <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="font-serif text-xl font-semibold text-foreground">Accent Progress Tracker</h2>
        {!matrix.locked ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            loading={isCheckingConsent}
            onClick={handleStartAccentAssessment}
          >
            Log New Check-In
          </Button>
        ) : null}
      </div>

      <p className="mt-1 text-sm text-muted-foreground">
        Month 1 baseline vs. your current progress across the four accent metrics.
      </p>

      <div className="mt-6 overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[420px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-surface text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <th className="sticky left-0 z-10 bg-surface px-4 py-3">Metric</th>
              <th className="px-4 py-3">Month 1 (Baseline)</th>
              <th className="px-4 py-3">Month 3 (Current)</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((row) => {
              const trendStyle = row.trend ? TREND_STYLES[row.trend] : null;
              const TrendIcon = trendStyle?.icon;

              return (
                <tr
                  key={row.key}
                  className={cn("border-b border-border last:border-b-0", trendStyle?.rowClass)}
                >
                  <td className="sticky left-0 z-10 bg-surface-elevated px-4 py-3 font-medium text-foreground">
                    {row.label}
                  </td>
                  <td className="px-4 py-3 text-foreground">{row.month1_score}%</td>
                  <td className="px-4 py-3">
                    {matrix.locked ? (
                      <span className="flex items-center gap-1.5 text-muted-foreground">
                        <Lock className="h-3.5 w-3.5" aria-hidden="true" />
                        Data unlocking in {matrix.days_until_unlock} days
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 text-foreground">
                        {row.month3_score}%
                        {TrendIcon ? (
                          <TrendIcon
                            className={cn("h-3.5 w-3.5", trendStyle?.iconClass)}
                            aria-hidden="true"
                          />
                        ) : null}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {!matrix.locked
        ? metrics
            .filter((row) => row.trend === "degraded" && row.tune_up_prompt)
            .map((row) => (
              <div
                key={row.key}
                className="mt-4 flex items-start gap-2.5 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-foreground"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
                {row.tune_up_prompt}
              </div>
            ))
        : null}

      <AccentCheckInModal
        open={isCheckInOpen}
        onClose={() => setIsCheckInOpen(false)}
        onSuccess={handleCheckInSuccess}
      />

      <VoiceConsentDisclosureModal
        open={isConsentOpen}
        onClose={() => setIsConsentOpen(false)}
        onAccepted={handleConsentAccepted}
      />

      <MicrophoneCheckModal
        open={isMicCheckOpen}
        onClose={() => setIsMicCheckOpen(false)}
        onPassed={handleMicCheckPassed}
      />
    </div>
  );
}
