import { afterEach, describe, expect, it, vi } from "vitest";
import { getSnapshot, getServerSnapshot, setTokens, subscribe } from "./tokenStore";
import type { Tokens } from "./types";

const TOKEN_KEY = "captureos.tokens";

const sampleTokens: Tokens = {
  accessToken: "access-123",
  refreshToken: "refresh-456",
  tokenType: "Bearer",
};

afterEach(() => {
  setTokens(null);
});

describe("tokenStore", () => {
  it("persists tokens to localStorage and reflects them in the snapshot", () => {
    setTokens(sampleTokens);
    expect(getSnapshot()).toEqual(sampleTokens);
    expect(JSON.parse(window.localStorage.getItem(TOKEN_KEY)!)).toEqual(sampleTokens);
  });

  it("clears the snapshot and localStorage when set to null", () => {
    setTokens(sampleTokens);
    setTokens(null);
    expect(getSnapshot()).toBeNull();
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("notifies subscribers on every change", () => {
    const listener = vi.fn();
    const unsubscribe = subscribe(listener);

    setTokens(sampleTokens);
    expect(listener).toHaveBeenCalledTimes(1);

    setTokens(null);
    expect(listener).toHaveBeenCalledTimes(2);

    unsubscribe();
    setTokens(sampleTokens);
    expect(listener).toHaveBeenCalledTimes(2); // no longer subscribed
  });

  it("returns null for the server snapshot (SSR/hydration safety)", () => {
    setTokens(sampleTokens);
    expect(getServerSnapshot()).toBeNull();
  });
});
