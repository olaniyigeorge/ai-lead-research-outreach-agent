"use client";

type Tone = "positive" | "neutral" | "negative";

const TONE_STYLES: Record<Tone, { icon: string; iconClass: string }> = {
  positive: { icon: "✓", iconClass: "bg-emerald-100 text-emerald-700" },
  neutral: { icon: "+", iconClass: "bg-sky-100 text-sky-700" },
  negative: { icon: "✕", iconClass: "bg-rose-100 text-rose-700" },
};

export function EditableCriteriaList({
  items,
  tone,
  onChange,
  addLabel = "Add",
}: {
  items: string[];
  tone: Tone;
  onChange: (items: string[]) => void;
  addLabel?: string;
}) {
  const style = TONE_STYLES[tone];

  function update(index: number, value: string) {
    const next = [...items];
    next[index] = value;
    onChange(next);
  }

  function remove(index: number) {
    onChange(items.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-2">
      {items.map((item, i) => (
        <div key={i} className="flex items-start gap-2">
          <span
            className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${style.iconClass}`}
          >
            {style.icon}
          </span>
          <input
            value={item}
            onChange={(e) => update(i, e.target.value)}
            className="flex-1 rounded-lg border border-surface-border bg-background px-2 py-1 text-sm text-foreground outline-none focus:border-primary-accent"
          />
          <button
            type="button"
            onClick={() => remove(i)}
            aria-label="Remove"
            className="mt-1 text-xs text-muted-text hover:text-red-600"
          >
            ×
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...items, ""])}
        className="pl-7 text-xs font-medium text-primary-accent hover:underline"
      >
        + {addLabel}
      </button>
    </div>
  );
}
