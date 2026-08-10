import { describe, expect, it } from "vitest";
import { INDUSTRY_OPTIONS, isKnownIndustry } from "./industries";

describe("isKnownIndustry", () => {
  it("accepts every option in the shared list", () => {
    for (const option of INDUSTRY_OPTIONS) {
      expect(isKnownIndustry(option)).toBe(true);
    }
  });

  it("rejects free text that isn't in the list (the 'Other' escape hatch)", () => {
    expect(isKnownIndustry("Underwater Basket Weaving")).toBe(false);
    expect(isKnownIndustry("")).toBe(false);
  });

  it("is case-sensitive against the canonical labels", () => {
    expect(isKnownIndustry("technology & software")).toBe(false);
  });
});
