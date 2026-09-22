export interface StatusConfig {
  label: string;
  badgeClass: string;
  dotClass: string;
  isTransient?: boolean;
}

export const RUN_STATUS_CONFIG: Record<string, StatusConfig> = {
  draft: {
    label: "Draft",
    badgeClass: "bg-surface-base text-muted-text border-surface-border",
    dotClass: "bg-muted-text",
  },
  awaiting_icp_confirmation: {
    label: "Awaiting Confirmation",
    badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
    dotClass: "bg-amber-500",
  },
  queued: {
    label: "Queued",
    badgeClass: "bg-primary-accent/10 text-primary-accent border-primary-accent/20",
    dotClass: "bg-primary-accent animate-pulse",
    isTransient: true,
  },
  running: {
    label: "Running",
    badgeClass: "bg-primary-accent/10 text-primary-accent border-primary-accent/20",
    dotClass: "bg-primary-accent animate-pulse",
    isTransient: true,
  },
  partially_completed: {
    label: "Partially Completed",
    badgeClass: "bg-amber-50 text-amber-700 border-amber-200",
    dotClass: "bg-amber-500",
  },
  completed: {
    label: "Completed",
    badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200",
    dotClass: "bg-emerald-500",
  },
  failed: {
    label: "Failed",
    badgeClass: "bg-rose-50 text-rose-700 border-rose-200",
    dotClass: "bg-rose-500",
  },
  canceled: {
    label: "Canceled",
    badgeClass: "bg-surface-base text-muted-text border-surface-border",
    dotClass: "bg-muted-text",
  },
};

export function getRunStatusConfig(status: string): StatusConfig {
  return (
    RUN_STATUS_CONFIG[status] || {
      label: status,
      badgeClass: "bg-surface-base text-muted-text border-surface-border",
      dotClass: "bg-muted-text",
    }
  );
}
