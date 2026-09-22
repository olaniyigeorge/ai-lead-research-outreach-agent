import { getRunStatusConfig } from "@/lib/run-status";

export function RunStatusBadge({ status }: { status: string }) {
  const config = getRunStatusConfig(status);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${config.badgeClass}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${config.dotClass}`} />
      {config.label}
    </span>
  );
}
