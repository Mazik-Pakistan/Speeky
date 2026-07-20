/**
 * Code-Switch Coaching Sensitivity Settings (US-59). The GitHub issue
 * shipped with no description or acceptance criteria beyond its title
 * ("Opt-Out / Adjust"), and there's no backend field or endpoint for it —
 * stored client-side.
 *
 * TODO(backend): add a `codeSwitchCoaching` preference (enabled + a
 * sensitivity enum) to the User model + a PATCH endpoint, then replace
 * this localStorage shim.
 */

export type CodeSwitchSensitivity = "low" | "medium" | "high";

export interface CodeSwitchSettings {
  enabled: boolean;
  sensitivity: CodeSwitchSensitivity;
}

export const CODE_SWITCH_SENSITIVITY_OPTIONS: {
  id: CodeSwitchSensitivity;
  label: string;
  description: string;
}[] = [
  { id: "low", label: "Low", description: "Only flag frequent, disruptive switching." },
  { id: "medium", label: "Medium", description: "Balanced — the default for most learners." },
  { id: "high", label: "High", description: "Flag even occasional code-switching." },
];

const DEFAULT_SETTINGS: CodeSwitchSettings = { enabled: true, sensitivity: "medium" };
const storageKey = (userId: string) => `speeky:code-switch:${userId}`;

export function getCodeSwitchSettings(userId: string): CodeSwitchSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const raw = window.localStorage.getItem(storageKey(userId));
    return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function setCodeSwitchSettings(userId: string, settings: CodeSwitchSettings) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(storageKey(userId), JSON.stringify(settings));
}
