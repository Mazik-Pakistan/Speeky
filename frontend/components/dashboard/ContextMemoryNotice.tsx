"use client";

import * as React from "react";
import Link from "next/link";
import { Brain, X } from "lucide-react";

/** Shown once per browser, the first time a user reaches a memory-backed feature —
 *  explains that context from past sessions carries forward, and points at the Profile
 *  toggle that turns it off. localStorage-gated, not a backend preference: this is purely
 *  "has this explainer been seen", same idiom as lib/cameraReadiness.ts/voiceReadiness.ts's
 *  local caches. `storageKey` differs per feature so dismissing one doesn't hide the other. */
export function ContextMemoryNotice({
  storageKey,
  message,
}: {
  storageKey: string;
  message: string;
}) {
  const [dismissed, setDismissed] = React.useState(true); // hidden until the effect below confirms otherwise

  React.useEffect(() => {
    setDismissed(window.localStorage.getItem(storageKey) === "1");
  }, [storageKey]);

  function handleDismiss() {
    window.localStorage.setItem(storageKey, "1");
    setDismissed(true);
  }

  if (dismissed) return null;

  return (
    <div className="flex items-start gap-2.5 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-foreground">
      <Brain className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
      <p className="flex-1">
        {message}{" "}
        <Link
          href="/dashboard/profile"
          className="font-medium text-primary underline-offset-2 hover:underline"
        >
          Manage in Profile → Memory
        </Link>
        .
      </p>
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss"
        className="shrink-0 text-muted-foreground hover:text-foreground"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}
