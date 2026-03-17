import { useEffect, useRef, useState } from "react";
import { fetchOverview } from "../services/api";

const POLLING_INTERVAL_MS = 2000;

function selectChannelPayload(snapshot, channel, babyId) {
  if (!snapshot) {
    return null;
  }

  if (channel === "baby") {
    const babies = snapshot.babies || [];
    const selectedBaby = babies.find((item) => item.id === babyId) || babies[0] || null;
    const alerts = selectedBaby
      ? (snapshot.alerts || []).filter((alert) => alert.babyId === selectedBaby.id)
      : snapshot.alerts || [];

    return {
      baby: selectedBaby,
      babies,
      alerts
    };
  }

  return snapshot;
}

function createSnapshotSignature(snapshot) {
  const babies = (snapshot?.babies || []).map((baby) =>
    [
      baby.id,
      baby.lastUpdated,
      baby.vitals?.heartRate,
      baby.vitals?.spo2,
      baby.vitals?.temperature,
      baby.vitals?.respiration,
      baby.riskScore
    ].join(":")
  );
  const alerts = (snapshot?.alerts || []).map((alert) => `${alert.id}:${alert.timestamp}`);

  return [snapshot?.generated_at || "", babies.join("|"), alerts.join("|")].join("~");
}

export function useWebSocket({ channel = "overview", babyId } = {}) {
  const pollingTimerRef = useRef(null);
  const pulseTimerRef = useRef(null);
  const lastSnapshotSignatureRef = useRef("");
  const [connectionState, setConnectionState] = useState("polling");
  const [snapshot, setSnapshot] = useState(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
  const [hasFreshUpdate, setHasFreshUpdate] = useState(false);

  useEffect(() => {
    let isMounted = true;

    function applySnapshot(nextSnapshot) {
      if (!isMounted || !nextSnapshot) {
        return;
      }

      const nextSignature = createSnapshotSignature(nextSnapshot);
      if (nextSignature && nextSignature === lastSnapshotSignatureRef.current) {
        return;
      }

      lastSnapshotSignatureRef.current = nextSignature;
      setSnapshot(nextSnapshot);
      setLastUpdatedAt(new Date());
      setHasFreshUpdate(true);

      if (pulseTimerRef.current) {
        window.clearTimeout(pulseTimerRef.current);
      }

      pulseTimerRef.current = window.setTimeout(() => {
        setHasFreshUpdate(false);
      }, 900);
    }

    async function loadSnapshot() {
      try {
        const overview = await fetchOverview();
        if (!isMounted) {
          return;
        }

        console.log("FETCH OK:", overview);
        setConnectionState("polling");
        applySnapshot(overview);
      } catch (error) {
        console.error("FETCH ERROR:", error);
        if (isMounted) {
          setConnectionState("error");
        }
      }
    }

    loadSnapshot();
    pollingTimerRef.current = window.setInterval(() => {
      loadSnapshot();
    }, POLLING_INTERVAL_MS);

    return () => {
      isMounted = false;
      if (pollingTimerRef.current) {
        window.clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }

      if (pulseTimerRef.current) {
        window.clearTimeout(pulseTimerRef.current);
      }
    };
  }, []);

  const data = selectChannelPayload(snapshot, channel, babyId);
  return { data, connectionState, lastUpdatedAt, hasFreshUpdate };
}
