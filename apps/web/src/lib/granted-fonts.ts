// Granted design-system fonts, loaded via next/font/google so they are
// self-hosted (no runtime requests to Google) and exposed as CSS variables.
// These variables are consumed by the Granted theme tokens in granted.css.
//
//   --font-granted-serif  → Instrument Serif (display: big $ numbers, h1/h2)
//   --font-granted-sans   → Hanken Grotesk (body/UI, weights 400–800)
//   --font-granted-mono   → JetBrains Mono (eyebrow labels / mono)

import { Hanken_Grotesk, Instrument_Serif, JetBrains_Mono } from "next/font/google";

export const grantedSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-granted-serif",
  display: "swap",
});

export const grantedSans = Hanken_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-granted-sans",
  display: "swap",
});

export const grantedMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-granted-mono",
  display: "swap",
});

// Convenience: all three font variables joined for a wrapper className.
export const grantedFontVars = `${grantedSerif.variable} ${grantedSans.variable} ${grantedMono.variable}`;
