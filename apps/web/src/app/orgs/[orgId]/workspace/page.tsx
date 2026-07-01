import { redirect } from "next/navigation";

// The workspace landing redirects to Find — the default surface for the CaptureOS
// experience. (Auth gating lives in the workspace shell that wraps the tab.)
export default async function WorkspaceIndex({
  params,
}: {
  params: Promise<{ orgId: string }>;
}) {
  const { orgId } = await params;
  redirect(`/orgs/${orgId}/workspace/find`);
}
