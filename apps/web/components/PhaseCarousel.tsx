"use client";

export function PhaseCarousel({
  activeKey,
  direction,
  children,
}: {
  activeKey: string;
  direction: 1 | -1;
  children: React.ReactNode;
}) {
  return (
    <div className="overflow-hidden">
      <div key={activeKey} className={direction === 1 ? "animate-slide-in-right" : "animate-slide-in-left"}>
        {children}
      </div>
    </div>
  );
}
