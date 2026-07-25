import { api } from "./api";

/** Notification frequency controls & quiet hours (US-169). */

export type NotificationCadence = "off" | "remind_if_not_practiced" | "always";

export interface NotificationPreferences {
  user_id: string;
  quiet_hours_start: string; // "HH:MM"
  quiet_hours_end: string; // "HH:MM"
  cadence: NotificationCadence;
  updated_at: string;
  device_id: string | null;
}

export interface PendingInAppItem {
  id: string;
  type: string;
  message: string;
  created_at: string;
}

// Stable per-browser id so quiet-hours prefs set from this device are
// attributable when synced account-wide (E-04) — no login-device registry exists,
// so this is a lightweight stand-in stored in localStorage.
export function getDeviceId(): string {
  if (typeof window === "undefined") return "server";
  const KEY = "speeky:device-id";
  let id = window.localStorage.getItem(KEY);
  if (!id) {
    id = `web_${Math.random().toString(36).slice(2, 10)}`;
    window.localStorage.setItem(KEY, id);
  }
  return id;
}

export function getNotificationPreferences() {
  return api<NotificationPreferences>("/notifications/preferences");
}

export function updateNotificationPreferences(data: {
  quiet_hours_start: string;
  quiet_hours_end: string;
  cadence: NotificationCadence;
}) {
  return api<NotificationPreferences>("/notifications/preferences", {
    method: "PATCH",
    body: JSON.stringify({ ...data, device_id: getDeviceId() }),
  });
}

export function getPendingInApp() {
  return api<{ items: PendingInAppItem[] }>("/notifications/pending");
}

export function ackPendingInApp(itemId: string) {
  return api<{ items: PendingInAppItem[] }>("/notifications/pending/ack", {
    method: "POST",
    body: JSON.stringify({ item_id: itemId }),
  });
}
