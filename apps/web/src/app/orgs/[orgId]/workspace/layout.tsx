import type { ReactNode } from "react";

import { WorkspaceShell } from "@/components/granted/WorkspaceShell";
import { grantedFontVars } from "@/lib/granted-fonts";

// Granted workspace layout. Applies the dark Granted theme (`.granted` scope)
// and the three next/font variables to a wrapper around the four tab surfaces
// (Find / Copilot / Pursue / Stay eligible) plus the in-shell header. Existing
// CaptureOS routes outside this segment keep their neutral theme untouched.
export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return (
    <div className={`granted ${grantedFontVars}`}>
      <WorkspaceShell>{children}</WorkspaceShell>
    </div>
  );
}
