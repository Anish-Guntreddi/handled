"use client";

import {
  useState,
  type CSSProperties,
  type InputHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

// Granted text inputs. On focus they take the green ring from the design
// (border #2E9E66 + 3px green glow). Shared style between Input and Textarea.

const FIELD_BASE: CSSProperties = {
  width: "100%",
  border: "1px solid var(--gr-border-input)",
  borderRadius: 9,
  outline: "none",
  fontFamily: "var(--gr-font-sans)",
  fontSize: 15,
  padding: "13px 15px",
  color: "var(--gr-text)",
  background: "var(--gr-input)",
};

const FOCUS: CSSProperties = {
  borderColor: "var(--gr-green)",
  boxShadow: "0 0 0 3px rgba(46,158,102,.22)",
};

export function Input({
  style,
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  const [focused, setFocused] = useState(false);
  return (
    <input
      {...rest}
      onFocus={(e) => {
        setFocused(true);
        rest.onFocus?.(e);
      }}
      onBlur={(e) => {
        setFocused(false);
        rest.onBlur?.(e);
      }}
      style={{ ...FIELD_BASE, ...(focused ? FOCUS : null), ...style }}
    />
  );
}

export function Textarea({
  style,
  rows = 3,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const [focused, setFocused] = useState(false);
  return (
    <textarea
      {...rest}
      rows={rows}
      onFocus={(e) => {
        setFocused(true);
        rest.onFocus?.(e);
      }}
      onBlur={(e) => {
        setFocused(false);
        rest.onBlur?.(e);
      }}
      style={{ ...FIELD_BASE, resize: "none", lineHeight: 1.55, ...(focused ? FOCUS : null), ...style }}
    />
  );
}
