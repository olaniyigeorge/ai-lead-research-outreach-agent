"use client";

export type StageStatus = "completed" | "current" | "running" | "upcoming";

export type Stage = {
  id: string;
  label: string;
  status: StageStatus;
};

const STATUS_DOT: Record<StageStatus, string> = {
  completed: "bg-emerald-500",
  current: "bg-primary-accent animate-pulse",
  running: "bg-sky-500 animate-pulse",
  upcoming: "bg-surface-border",
};

const STATUS_TEXT: Record<StageStatus, string> = {
  completed: "text-foreground",
  current: "text-primary-accent",
  running: "text-sky-600",
  upcoming: "text-muted-text",
};

export function StageStepper({
  stages,
  activeId,
  onSelect,
}: {
  stages: Stage[];
  activeId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="sticky top-0 z-10 border-b border-surface-border bg-surface-card/95 backdrop-blur">
      <div className="mx-auto flex max-w-3xl items-center gap-1 overflow-x-auto px-4 py-3 sm:px-8">
        {stages.map((stage, i) => (
          <div key={stage.id} className="flex items-center gap-1">
            {i > 0 && <span className="mx-1 h-px w-6 shrink-0 bg-surface-border" />}
            <button
              type="button"
              onClick={() => onSelect(stage.id)}
              className={`flex items-center gap-2 whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                activeId === stage.id ? "bg-surface-base" : "hover:bg-surface-base"
              } ${STATUS_TEXT[stage.status]}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[stage.status]}`} />
              {stage.label}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
