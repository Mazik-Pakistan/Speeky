"use client";

import * as React from "react";
import { Sparkles, X } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { ackPendingInApp, getPendingInApp, type PendingInAppItem } from "@/lib/notifications";

/**
 * Surfaces queued in-app messages on next open: missed-streak summaries for users
 * with reminders off (US-169 E-02), and any milestone pushes that were deferred
 * during quiet hours and have since been released (US-169 E-03).
 */
export function PendingNotificationsBanner() {
  const { user } = useAuth();
  const [items, setItems] = React.useState<PendingInAppItem[]>([]);

  React.useEffect(() => {
    if (!user) return;
    getPendingInApp()
      .then((res) => setItems(res.items))
      .catch(() => {});
  }, [user]);

  if (items.length === 0) return null;

  async function handleAck(id: string) {
    setItems((prev) => prev.filter((i) => i.id !== id));
    try {
      await ackPendingInApp(id);
    } catch {
      // best-effort — item already removed from view
    }
  }

  return (
    <div className="mb-6 flex flex-col gap-2">
      {items.map((item) => (
        <div
          key={item.id}
          className="flex items-start gap-3 rounded-xl border border-border bg-surface-elevated px-4 py-3 text-sm shadow-sm"
        >
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
          <p className="flex-1 text-foreground">{item.message}</p>
          <button
            type="button"
            onClick={() => handleAck(item.id)}
            aria-label="Dismiss"
            className="shrink-0 rounded-lg p-1 text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      ))}
    </div>
  );
}
