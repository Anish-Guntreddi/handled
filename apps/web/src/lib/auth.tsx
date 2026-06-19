"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";

import { apiFetch } from "./api";
import { getServerSnapshot, getSnapshot, setTokens, subscribe } from "./tokenStore";
import type { Tokens } from "./types";

// Returns false on the server + during hydration, true afterward — without setState.
const noopSubscribe = () => () => {};
function useHydrated(): boolean {
  return useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
}

type AuthContextValue = {
  tokens: Tokens | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    fullName?: string,
    orgName?: string,
  ) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const tokens = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const hydrated = useHydrated();

  const login = useCallback(async (email: string, password: string) => {
    const t = await apiFetch<Tokens>("/auth/login", {
      method: "POST",
      body: { email, password },
    });
    setTokens(t);
  }, []);

  const register = useCallback(
    async (email: string, password: string, fullName?: string, orgName?: string) => {
      const t = await apiFetch<Tokens>("/auth/register", {
        method: "POST",
        body: { email, password, fullName, orgName },
      });
      setTokens(t);
    },
    [],
  );

  const logout = useCallback(() => {
    setTokens(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      tokens,
      loading: !hydrated,
      isAuthenticated: tokens !== null,
      login,
      register,
      logout,
    }),
    [tokens, hydrated, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
