"use client";

import * as React from "react";
import { Languages } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import {
  CODE_SWITCH_SENSITIVITY_OPTIONS,
  getCodeSwitchSettings,
  setCodeSwitchSettings,
  type CodeSwitchSettings,
} from "@/lib/code-switch";

/** US-59: Code-Switch Coaching Sensitivity Settings (Opt-Out / Adjust) — frontend-only, see lib/code-switch.ts. */
export function CodeSwitchSection() {
  const { user } = useAuth();
  const [settings, setSettings] = React.useState<CodeSwitchSettings | null>(null);

  React.useEffect(() => {
    if (!user) return;
    setSettings(getCodeSwitchSettings(user.id));
  }, [user]);

  if (!user || !settings) return null;

  function update(next: CodeSwitchSettings) {
    setCodeSwitchSettings(user!.id, next);
    setSettings(next);
  }

  return (
    <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-secondary text-primary">
            <Languages className="h-4 w-4" aria-hidden="true" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              Code-Switch Coaching
            </h2>
            <p className="text-sm text-muted-foreground">
              Get gentle nudges when you switch languages mid-sentence during
              practice.
            </p>
          </div>
        </div>
        <Switch
          checked={settings.enabled}
          onCheckedChange={(enabled) => update({ ...settings, enabled })}
          label="Enable code-switch coaching"
          hideLabel
        />
      </div>

      <div
        className={cn(
          "mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3",
          !settings.enabled && "pointer-events-none opacity-50",
        )}
      >
        {CODE_SWITCH_SENSITIVITY_OPTIONS.map((option) => (
          <button
            key={option.id}
            type="button"
            onClick={() => update({ ...settings, sensitivity: option.id })}
            className={cn(
              "rounded-xl border p-3 text-left transition-colors",
              settings.sensitivity === option.id
                ? "border-primary bg-secondary"
                : "border-border hover:bg-surface",
            )}
          >
            <p className="text-sm font-semibold text-foreground">{option.label}</p>
            <p className="mt-1 text-xs text-muted-foreground">{option.description}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
