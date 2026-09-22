"use client";

import { useEffect, useState } from "react";

export type StageStatus = "completed" | "current" | "upcoming";

export type Stage = {
  id: string;
  label: string;
  status: StageStatus;
};

const STATUS_DOT: Record<StageStatus, string> = {
  completed: "bg-emerald-500",
  current: "bg-primary-accent animate-pulse",
  upcoming: "bg-surface-border",
};

const STATUS_TEXT: Record<StageStatus, string> = {
  completed: "text-foreground",
  current: "text-primary-accent",
  upcoming: "text-muted-text",
};

function scrollToSection(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function StageStepper({ stages }: { stages: Stage[] }) {
  const [activeId, setActiveId] = useState(stages[0]?.id);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length > 0) {
          setActiveId(visible[0].target.id);
        }
      },
      { rootMargin: "-20% 0px -70% 0px" }
    );

    stages.forEach((stage) => {
      const el = document.getElementById(stage.id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [stages]);

  return (
    <div className="sticky top-0 z-10 border-b border-surface-border bg-surface-card/95 backdrop-blur">
      <div className="mx-auto flex max-w-3xl items-center gap-1 overflow-x-auto px-4 py-3 sm:px-8">
        {stages.map((stage, i) => (
          <div key={stage.id} className="flex items-center gap-1">
            {i > 0 && <span className="mx-1 h-px w-6 shrink-0 bg-surface-border" />}
            <button
              type="button"
              onClick={() => scrollToSection(stage.id)}
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
