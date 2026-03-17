import { memo, useEffect } from "react";

const severityStyles = {
  low: "border-[#d7ebdf] bg-[#f4fbf6] text-stable",
  warning: "border-[#f0e1be] bg-[#fffaf0] text-warning",
  critical: "border-[#f1d1d1] bg-[#fff5f5] text-critical"
};

function normalizeSeverity(value) {
  if (value === "critical" || value === "warning" || value === "low") {
    return value;
  }

  return "warning";
}

function mapTypeToSeverity(value) {
  if (value === "prediction") {
    return "critical";
  }

  if (value === "threshold") {
    return "warning";
  }

  return "low";
}

function SingleAlert({ message, severity = "warning", onClose }) {
  useEffect(() => {
    if (!message || !onClose) {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      onClose();
    }, 5000);

    return () => {
      window.clearTimeout(timer);
    };
  }, [message, onClose]);

  if (!message) {
    return null;
  }

  const tone = normalizeSeverity(severity);

  return (
    <div className="fixed right-6 top-6 z-50 w-full max-w-sm animate-slide-up">
      <div className={`rounded-[24px] border p-4 shadow-panel ${severityStyles[tone]}`}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em]">{tone}</p>
            <p className="mt-2 text-sm leading-6 text-ink">{message}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-current/20 px-2 py-1 text-xs font-semibold transition hover:bg-white/70"
            aria-label="Close alert"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function AlertList({ alerts }) {
  const latestAlerts = alerts.slice(0, 4);

  return (
    <section className="rounded-[30px] border border-[#dbe7ed] bg-white p-5 shadow-panel">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Active Alerts</h2>
          <p className="text-sm text-slate">Threshold breaches and early prediction warnings.</p>
        </div>
        <div className="rounded-full bg-[#fff4d7] px-3 py-1 text-xs font-semibold text-warning">Visual Alert</div>
      </div>
      <div className="space-y-3">
        {latestAlerts.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-[#dbe7ed] p-4 text-sm text-slate">No active alerts.</div>
        ) : (
          latestAlerts.map((alert) => {
            const tone = mapTypeToSeverity(alert.type);

            return (
              <div key={alert.id} className={`animate-slide-up rounded-2xl border p-4 ${severityStyles[tone]}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold">
                      {alert.title} - {alert.babyId}
                    </p>
                    <p className="mt-1 text-sm text-ink/80">{alert.message}</p>
                  </div>
                  <div className="rounded-full bg-white/80 px-2 py-1 text-xs font-semibold uppercase tracking-[0.2em]">
                    {tone}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}

function AlertPopupComponent({ message, severity = "warning", onClose, alerts }) {
  if (Array.isArray(alerts)) {
    return <AlertList alerts={alerts} />;
  }

  return <SingleAlert message={message} severity={severity} onClose={onClose} />;
}

const AlertPopup = memo(AlertPopupComponent);

export default AlertPopup;