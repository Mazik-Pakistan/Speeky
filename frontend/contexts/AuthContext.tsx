"use client";

import * as React from "react";
import { getCurrentUser, logout as logoutRequest, type AuthUser } from "@/lib/auth";

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  setUser: (user: AuthUser | null) => void;
  logout: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);

  React.useEffect(() => {
    let cancelled = false;

    getCurrentUser()
      .then((data) => {
        if (!cancelled) setUser(data.user);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // lib/api.ts fires this when a 401 survives a refresh attempt (refresh
  // token itself expired/revoked) — clear state so dashboard guards send
  // the user back to /login instead of leaving stale "logged in" UI up
  // while every API call silently fails.
  React.useEffect(() => {
    function handleSessionExpired() {
      setUser(null);
    }
    window.addEventListener("speeky:session-expired", handleSessionExpired);
    return () => window.removeEventListener("speeky:session-expired", handleSessionExpired);
  }, []);

  const logout = React.useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      // Session may already be invalid server-side — clear it client-side regardless.
    }
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, setUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
