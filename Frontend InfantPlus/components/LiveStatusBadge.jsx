function formatTime(lastUpdatedAt) {
  if (!lastUpdatedAt) {
    return "Waiting for feed";
  }

  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(lastUpdatedAt);
}

export default function LiveStatusBadge({ connectionState, lastUpdatedAt, hasFreshUpdate = false }) {
  const isLive = connectionState === "open" || connectionState === "polling";
  const toneClassName = isLive
    ? "border-[#d5eadf] bg-[#f5fbf7] text-stable"
    : "border-[#f0e1be] bg-[#fffaf0] text-warning";

  return (
    <div className={`inline-flex items-center gap-3 rounded-full border px-4 py-2 text-sm shadow-sm ${toneClassName}`}>
      <span
        className={`h-2.5 w-2.5 rounded-full ${isLive ? "bg-stable" : "bg-warning"} ${
          hasFreshUpdate ? "animate-pulse-soft" : ""
        }`}
      />
      <span className="font-semibold uppercase tracking-[0.22em]">{isLive ? "Live" : connectionState}</span>
      <span className="text-xs text-slate">Updated {formatTime(lastUpdatedAt)}</span>
    </div>
  );
}
