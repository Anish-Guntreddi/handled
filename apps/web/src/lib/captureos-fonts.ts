// CaptureOS design-system fonts, loaded via next/font/google so they are
// self-hosted (no runtime requests to Google) and exposed as CSS variables.
// These variables are consumed by the CaptureOS theme tokens in captureos.css.
//
//   --font-captureos-serif  → Instrument Serif (display: big $ numbers, h1/h2)
//   --font-captureos-sans   → Hanken Grotesk (body/UI, weights 400–800)
//   --font-captureos-mono   → JetBrains Mono (eyebrow labels / mono)

import { Hanken_Grotesk, Instrument_Serif, JetBrains_Mono } from "next/font/google";

export const captureosSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-captureos-serif",
  display: "swap",
});

export const captureosSans = Hanken_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-captureos-sans",
  display: "swap",
});

export const captureosMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-captureos-mono",
  display: "swap",
});

// Convenience: all three font variables joined for a wrapper className.
export const captureosFontVars = `${captureosSerif.variable} ${captureosSans.variable} ${captureosMono.variable}`;
