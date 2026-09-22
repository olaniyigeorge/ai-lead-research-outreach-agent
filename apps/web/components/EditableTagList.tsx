"use client";

import { useState } from "react";

export function EditableTagList({
  items,
  onChange,
  placeholder = "Add and press Enter",
}: {
  items: string[];
  onChange: (items: string[]) => void;
  placeholder?: string;
}) {
  const [draft, setDraft] = useState("");

  function commit() {
    const value = draft.trim();
    if (value && !items.includes(value)) {
      onChange([...items, value]);
    }
    setDraft("");
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {items.map((item) => (
        <span
          key={item}
          className="flex items-center gap-1 rounded-full border border-surface-border bg-surface-base px-2.5 py-0.5 text-xs text-foreground"
        >
          {item}
          <button
            type="button"
            onClick={() => onChange(items.filter((i) => i !== item))}
            aria-label={`Remove ${item}`}
            className="text-muted-text hover:text-red-600"
          >
            ×
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            commit();
          } else if (e.key === "Backspace" && draft === "" && items.length > 0) {
            onChange(items.slice(0, -1));
          }
        }}
        onBlur={commit}
        placeholder={placeholder}
        className="min-w-[8rem] flex-1 rounded-full border border-dashed border-surface-border bg-transparent px-2.5 py-0.5 text-xs text-foreground outline-none focus:border-primary-accent"
      />
    </div>
  );
}
