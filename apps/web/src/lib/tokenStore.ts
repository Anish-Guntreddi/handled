// External token store backed by localStorage, consumed via useSyncExternalStore.
// This is the React 19-idiomatic way to read browser storage without setState-in-effect
// and without hydration mismatches (getServerSnapshot returns null to match SSR).

import { setTokenGetter } from "./api";
import type { Tokens } from "./types";

const TOKEN_KEY = "captureos.tokens";
type Listener = () => void;
const listeners = new Set<Listener>();

function read(): Tokens | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(TOKEN_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Tokens;
  } catch {
    return null;
  }
}

// Stable cached snapshot (useSyncExternalStore requires reference stability).
let snapshot: Tokens | null = read();

// The api client pulls the access token synchronously from this store.
setTokenGetter(() => snapshot?.accessToken ?? null);

export function getSnapshot(): Tokens | null {
  return snapshot;
}

export function getServerSnapshot(): Tokens | null {
  return null;
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function setTokens(next: Tokens | null): void {
  snapshot = next;
  if (typeof window !== "undefined") {
    if (next) window.localStorage.setItem(TOKEN_KEY, JSON.stringify(next));
    else window.localStorage.removeItem(TOKEN_KEY);
  }
  for (const listener of listeners) listener();
}
