"use client";

import { useState } from "react";

type Tone = "positive" | "neutral" | "negative";

const TONE_STYLES: Record<Tone, { icon: string; iconClass: string }> = {
  positive: { icon: "✓", iconClass: "bg-emerald-100 text-emerald-700" },
  neutral: { icon: "+", iconClass: "bg-sky-100 text-sky-700" },
  negative: { icon: "✕", iconClass: "bg-rose-100 text-rose-700" },
};

export function CriteriaList({
  items,
  tone,
  emptyLabel = "None specified.",
  maxVisible = 4,
}: {
  items: string[];
  tone: Tone;
  emptyLabel?: string;
  maxVisible?: number;
}) {
  const [expanded, setExpanded] = useState(false);

  if (items.length === 0) {
    return <p className="text-sm text-muted-text">{emptyLabel}</p>;
  }

  const visible = expanded ? items : items.slice(0, maxVisible);
  const hiddenCount = items.length - visible.length;
  const style = TONE_STYLES[tone];

  return (
    <div className="space-y-2.5">
      {visible.map((item, i) => (
        <div key={i} className="flex items-start gap-3">
          <span
            className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${style.iconClass}`}
          >
            {style.icon}
          </span>
          <p className="text-sm leading-relaxed text-foreground">{item}</p>
        </div>
      ))}
      {items.length > maxVisible && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="pl-8 text-xs font-medium text-primary-accent hover:underline"
        >
          {expanded ? "Show less" : `Show ${hiddenCount} more`}
        </button>
      )}
    </div>
  );
}
