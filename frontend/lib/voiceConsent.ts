import { api } from "./api";

export const VOICE_CONSENT_POLICY_VERSION = "ACC-US-02-v1";

export interface VoiceConsentStatus {
  granted: boolean;
  policy_version: string;
  retention_days: number;
  raw_audio_retained: boolean;
  consented_at: string | null;
  withdrawn_at: string | null;
  raw_audio_deleted_at: string | null;
  region: string | null;
}

export interface VoiceSampleDeletionResult {
  deleted_audio_samples: number;
  raw_audio_retained: boolean;
  message: string;
}

export function getVoiceConsent() {
  return api<VoiceConsentStatus>("/voice-consent");
}

export function updateVoiceConsent(granted: boolean, region?: string) {
  return api<VoiceConsentStatus>("/voice-consent", {
    method: "PATCH",
    body: JSON.stringify({
      granted,
      policy_version: VOICE_CONSENT_POLICY_VERSION,
      region,
    }),
  });
}

export function deleteStoredVoiceSamples() {
  return api<VoiceSampleDeletionResult>("/voice-consent/voice-samples", {
    method: "DELETE",
  });
}