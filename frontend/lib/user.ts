import { api } from "./api";
import type { AuthUser } from "./auth";

export function updateProfile(data: { name?: string; email?: string }) {
  return api<{ user: AuthUser }>("/users/me", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function uploadAvatar(file: File) {
  const formData = new FormData();
  formData.append("avatar", file);
  return api<{ user: AuthUser }>("/users/me/avatar", {
    method: "PATCH",
    body: formData,
  });
}

export function deleteAccount(password: string) {
  return api<null>("/users/me", {
    method: "DELETE",
    body: JSON.stringify({ password }),
  });
}
