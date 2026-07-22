"use client";

import * as React from "react";
import { ChevronDown, ShieldCheck } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import {
  CONSENT_CATEGORIES,
  getConsentHistory,
  getConsentPreferences,
  setConsent,
  type ConsentHistoryEntry,
  type ConsentPreferences,
} from "@/lib/consent";

/** US-06: Privacy & Consent — frontend-only, see lib/consent.ts for the backend TODO. */
export function PrivacyConsentSection() {
  const { user } = useAuth();
  const [preferences, setPreferences] = React.useState<ConsentPreferences | null>(null);
  const [history, setHistory] = React.useState<ConsentHistoryEntry[]>([]);
  const [historyOpen, setHistoryOpen] = React.useState(false);

  React.useEffect(() => {
    if (!user) return;
    setPreferences(getConsentPreferences(user.id));
    setHistory(getConsentHistory(user.id));
  }, [user]);

  if (!user || !preferences) return null;

  function handleToggle(category: (typeof CONSENT_CATEGORIES)[number]["id"], granted: boolean) {
    const result = setConsent(user!.id, category, granted);
    setPreferences(result.preferences);
    setHistory(result.history);
  }

  return (
    <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-primary">
          <ShieldCheck className="h-4 w-4" aria-hidden="true" />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-foreground">Privacy &amp; Consent</h2>
          <p className="text-sm text-muted-foreground">
            Manage how your data is used. Changes are recorded to a viewable
            history below.
          </p>
        </div>
      </div>

      <div className="mt-4 flex flex-col divide-y divide-border border-t border-border">
        <div className="flex items-center justify-between py-3">
          <div>
            <p className="text-sm font-medium text-foreground">Essential Account Data</p>
            <p className="text-xs text-muted-foreground">
              Required to operate your account — can&apos;t be turned off.
            </p>
          </div>
          <Switch checked disabled onCheckedChange={() => {}} label="Essential Account Data" hideLabel />
        </div>
        {CONSENT_CATEGORIES.map((category) => (
          <div key={category.id} className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm font-medium text-foreground">{category.label}</p>
              <p className="text-xs text-muted-foreground">{category.description}</p>
            </div>
            <Switch
              checked={preferences[category.id]}
              onCheckedChange={(checked) => handleToggle(category.id, checked)}
              label={category.label}
              hideLabel
            />
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={() => setHistoryOpen((open) => !open)}
        className="mt-4 flex w-full items-center justify-between text-sm font-medium text-primary"
      >
        Consent history
        <ChevronDown
          className={cn("h-4 w-4 transition-transform", historyOpen && "rotate-180")}
          aria-hidden="true"
        />
      </button>
      {historyOpen ? (
        <ul className="mt-3 flex flex-col gap-2">
          {history.length === 0 ? (
            <li className="text-xs text-muted-foreground">No changes recorded yet.</li>
          ) : (
            history.map((entry, i) => (
              <li key={i} className="text-xs text-muted-foreground">
                {new Date(entry.timestamp).toLocaleString()} — {" "}
                {CONSENT_CATEGORIES.find((c) => c.id === entry.category)?.label ?? entry.category}{" "}
                {entry.granted ? "enabled" : "disabled"} (policy {entry.policyVersion})
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}
