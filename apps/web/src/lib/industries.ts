// Single source of truth for the industry picker — shared by the onboarding
// wizard (initial capture + post-scan Brain Review correction) and the legacy
// Company Brain override field, so the category list can't drift between
// surfaces. Broad, plain-language, roughly NAICS-sector-level: wide enough
// that most businesses match one directly, with "Other" as the guaranteed
// escape hatch for the rest.
export const INDUSTRY_OPTIONS = [
  "Technology & Software",
  "Professional & Consulting Services",
  "Healthcare & Life Sciences",
  "Manufacturing",
  "Construction",
  "Retail & E-commerce",
  "Agriculture & Food Production",
  "Transportation & Logistics",
  "Energy & Utilities",
  "Financial Services",
  "Real Estate",
  "Education",
  "Hospitality & Food Service",
  "Nonprofit & Social Services",
  "Media & Entertainment",
] as const;

export function isKnownIndustry(value: string): boolean {
  return (INDUSTRY_OPTIONS as readonly string[]).includes(value);
}
