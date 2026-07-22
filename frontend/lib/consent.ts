/**
 * Privacy & Consent (US-06). No ConsentPreference model exists in the
 * Prisma schema and no /api/consent endpoints exist, so this is stored
 * client-side with a full local audit trail, mirroring the shape a real
 * backend table would need.
 *
 * TODO(backend): add a ConsentPreference/ConsentHistory model (userId,
 * category, granted, policyVersion, createdAt) + GET/PATCH
 * /api/users/me/consent endpoints, then swap this localStorage shim for
 * real API calls. Keep the policyVersion field either way — the AC
 * requires every decision to be stored with the policy version it was
 * made under.
 */

import { PRIVACY_VERSION } from "./privacy-content";

export type ConsentCategory = "marketing" | "data_sharing" | "analytics";

export interface ConsentCategoryOption {
  id: ConsentCategory;
  label: string;
  description: string;
}

export const CONSENT_CATEGORIES: ConsentCategoryOption[] = [
  {
    id: "marketing",
    label: "Marketing Communications",
    description: "Product updates, tips, and promotional emails.",
  },
  {
    id: "data_sharing",
    label: "Data Sharing with Partners",
    description: "Share anonymized practice data with integration partners.",
  },
  {
    id: "analytics",
    label: "Usage Analytics",
    description: "Help us improve Speeky by sharing anonymized usage data.",
  },
];

export interface ConsentPreferences {
  marketing: boolean;
  data_sharing: boolean;
  analytics: boolean;
}

export interface ConsentHistoryEntry {
  category: ConsentCategory;
  granted: boolean;
  policyVersion: string;
  timestamp: string;
}

const DEFAULT_PREFERENCES: ConsentPreferences = {
  marketing: false,
  data_sharing: false,
  analytics: false,
};

const prefsKey = (userId: string) => `speeky:consent-prefs:${userId}`;
const historyKey = (userId: string) => `speeky:consent-history:${userId}`;

export function getConsentPreferences(userId: string): ConsentPreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const raw = window.localStorage.getItem(prefsKey(userId));
    return raw ? { ...DEFAULT_PREFERENCES, ...JSON.parse(raw) } : DEFAULT_PREFERENCES;
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function getConsentHistory(userId: string): ConsentHistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(historyKey(userId));
    return raw ? (JSON.parse(raw) as ConsentHistoryEntry[]) : [];
  } catch {
    return [];
  }
}

// Every decision is recorded with the current policy version and a
// timestamp (AC: "must be stored with its corresponding policy version").
export function setConsent(
  userId: string,
  category: ConsentCategory,
  granted: boolean
): { preferences: ConsentPreferences; history: ConsentHistoryEntry[] } {
  const preferences = { ...getConsentPreferences(userId), [category]: granted };
  const entry: ConsentHistoryEntry = {
    category,
    granted,
    policyVersion: PRIVACY_VERSION,
    timestamp: new Date().toISOString(),
  };
  const history = [entry, ...getConsentHistory(userId)];

  window.localStorage.setItem(prefsKey(userId), JSON.stringify(preferences));
  window.localStorage.setItem(historyKey(userId), JSON.stringify(history));

  return { preferences, history };
}
