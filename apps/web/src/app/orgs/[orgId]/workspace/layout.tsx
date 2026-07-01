import type { ReactNode } from "react";

import { WorkspaceShell } from "@/components/captureos/WorkspaceShell";
import { captureosFontVars } from "@/lib/captureos-fonts";

// CaptureOS workspace layout. Applies the dark CaptureOS theme (`.captureos` scope)
// and the three next/font variables to a wrapper around the four tab surfaces
// (Find / Copilot / Pursue / Stay eligible) plus the in-shell header. Existing
// CaptureOS routes outside this segment keep their neutral theme untouched.
export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return (
    <div className={`captureos ${captureosFontVars}`}>
      <WorkspaceShell>{children}</WorkspaceShell>
    </div>
  );
}
