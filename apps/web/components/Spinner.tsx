const SIZE_CLASSES: Record<"small" | "medium", string> = {
  small: "h-3.5 w-3.5 border-[1.5px]",
  medium: "h-5 w-5 border-2",
};

export function Spinner({
  size = "small",
  className = "",
}: {
  size?: "small" | "medium";
  className?: string;
}) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block shrink-0 animate-spin rounded-full border-current border-t-transparent text-current ${SIZE_CLASSES[size]} ${className}`}
    />
  );
}

export function LoadingLine({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="animate-fade-in flex min-h-screen items-center justify-center gap-2 bg-surface-base text-sm text-muted-text">
      <Spinner size="medium" />
      {label}
    </div>
  );
}
