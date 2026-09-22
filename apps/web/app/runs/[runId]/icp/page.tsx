import { redirect } from "next/navigation";

export default async function ICPLegacyRedirect({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  redirect(`/runs/${runId}#icp`);
}
