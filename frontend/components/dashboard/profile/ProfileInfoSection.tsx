"use client";

import * as React from "react";
import Image from "next/image";
import { Camera, ShieldCheck } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ApiError, API_ORIGIN } from "@/lib/api";
import { updateProfile, uploadAvatar } from "@/lib/user";
import { useAuth } from "@/contexts/AuthContext";
import { getInitials } from "@/lib/utils";

const ROLE_LABELS: Record<string, string> = {
  ADMIN: "Administrator",
  USER: "Learner",
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** US-04: editable name/email + avatar upload, both wired to the real backend. */
export function ProfileInfoSection() {
  const { user, setUser } = useAuth();
  const [name, setName] = React.useState(user?.name ?? "");
  const [email, setEmail] = React.useState(user?.email ?? "");
  const [fieldError, setFieldError] = React.useState<string | null>(null);
  const [formError, setFormError] = React.useState<string | null>(null);
  const [successMessage, setSuccessMessage] = React.useState<string | null>(null);
  const [isSaving, setIsSaving] = React.useState(false);
  const [isUploadingAvatar, setIsUploadingAvatar] = React.useState(false);
  const [avatarError, setAvatarError] = React.useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  if (!user) return null;

  const hasChanges = name.trim() !== user.name || email.trim() !== user.email;

  async function handleSave() {
    setFieldError(null);
    setFormError(null);
    setSuccessMessage(null);

    const trimmedName = name.trim();
    const trimmedEmail = email.trim();

    if (!trimmedName) {
      setFieldError("Name cannot be empty.");
      return;
    }
    if (!EMAIL_PATTERN.test(trimmedEmail)) {
      setFieldError("Enter a valid email address.");
      return;
    }

    setIsSaving(true);
    try {
      const payload: { name?: string; email?: string } = {};
      if (trimmedName !== user!.name) payload.name = trimmedName;
      if (trimmedEmail !== user!.email) payload.email = trimmedEmail;

      const { user: updated } = await updateProfile(payload);
      setUser(updated);
      setSuccessMessage("Profile updated.");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleAvatarChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setAvatarError(null);
    setIsUploadingAvatar(true);
    try {
      const { user: updated } = await uploadAvatar(file);
      setUser(updated);
    } catch (err) {
      setAvatarError(err instanceof ApiError ? err.message : "Couldn't upload that image.");
    } finally {
      setIsUploadingAvatar(false);
    }
  }

  const hasCustomAvatar = user.avatarUrl && user.avatarUrl !== "user.webp";

  return (
    <div className="rounded-2xl border border-border bg-surface-elevated p-6 shadow-sm">
      <div className="flex items-center gap-4">
        <div className="relative">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploadingAvatar}
            className="group relative flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full bg-secondary text-xl font-semibold text-primary disabled:opacity-70"
            aria-label="Change profile photo"
          >
            {hasCustomAvatar ? (
              <Image
                src={`${API_ORIGIN}/uploads/avatars/${user.avatarUrl}`}
                alt=""
                width={64}
                height={64}
                className="h-full w-full object-cover"
                unoptimized
              />
            ) : (
              getInitials(user.name)
            )}
            <span className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition-opacity group-hover:opacity-100">
              <Camera className="h-5 w-5 text-white" aria-hidden="true" />
            </span>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={handleAvatarChange}
          />
        </div>
        <div>
          <p className="text-lg font-semibold text-foreground">{user.name}</p>
          <span className="mt-1 inline-flex items-center gap-1.5 rounded-full bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
            {ROLE_LABELS[user.role] ?? user.role}
          </span>
        </div>
      </div>
      {avatarError ? <p className="mt-3 text-xs text-danger">{avatarError}</p> : null}

      <div className="mt-6 flex flex-col gap-4 border-t border-border pt-6">
        <Input
          label="Full Name"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <Input
          label="Email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        {fieldError ? <p className="text-sm text-danger">{fieldError}</p> : null}
        {formError ? <p className="text-sm text-danger">{formError}</p> : null}
        {successMessage ? (
          <p className="text-sm text-success">{successMessage}</p>
        ) : null}
        <Button
          type="button"
          size="sm"
          className="self-start"
          loading={isSaving}
          disabled={!hasChanges}
          onClick={handleSave}
        >
          Save Changes
        </Button>
      </div>
    </div>
  );
}
