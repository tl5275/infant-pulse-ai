import { useEffect, useRef, useState } from "react";
import { fetchOverview } from "../services/api";
import { createNICUSocket } from "../services/socket";

const POLLING_INTERVAL_MS = 2000;
const RECONNECT_DELAY_MS = 3000;
const SOCKET_TIMEOUT_MS = 1500;

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
  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const pollingTimerRef = useRef(null);
  const socketTimeoutRef = useRef(null);
  const pulseTimerRef = useRef(null);
  const lastSnapshotSignatureRef = useRef("");
  const [connectionState, setConnectionState] = useState("connecting");
  const [snapshot, setSnapshot] = useState(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
  const [hasFreshUpdate, setHasFreshUpdate] = useState(false);

  useEffect(() => {
    let isMounted = true;
    let shouldReconnect = true;

    function clearSocketTimeout() {
      if (socketTimeoutRef.current) {
        window.clearTimeout(socketTimeoutRef.current);
        socketTimeoutRef.current = null;
      }
    }

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
        applySnapshot(overview);
      } catch (error) {
        console.error("Failed to fetch live overview", error);
      }
    }

    function stopPolling() {
      if (pollingTimerRef.current) {
        window.clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    }

    function startPolling() {
      if (pollingTimerRef.current) {
        return;
      }

      setConnectionState("polling");
      loadSnapshot();
      pollingTimerRef.current = window.setInterval(() => {
        loadSnapshot();
      }, POLLING_INTERVAL_MS);
    }

    function scheduleReconnect() {
      if (!shouldReconnect || reconnectTimerRef.current) {
        return;
      }

      reconnectTimerRef.current = window.setTimeout(() => {
        reconnectTimerRef.current = null;
        connect();
      }, RECONNECT_DELAY_MS);
    }

    function connect() {
      clearSocketTimeout();

      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }

      const socket = createNICUSocket();
      socketRef.current = socket;
      setConnectionState("connecting");
      socketTimeoutRef.current = window.setTimeout(() => {
        if (socket.readyState !== WebSocket.OPEN) {
          console.log("WS failed -> fallback to polling");
          startPolling();
        }
      }, SOCKET_TIMEOUT_MS);

      socket.onopen = () => {
        clearSocketTimeout();
        stopPolling();
        setConnectionState("open");
      };

      socket.onmessage = (event) => {
        try {
          const nextSnapshot = JSON.parse(event.data);
          if (nextSnapshot?.event === "connected") {
            return;
          }

          applySnapshot(nextSnapshot);
        } catch (error) {
          console.error("Failed to parse WebSocket payload", error);
        }
      };

      socket.onerror = () => {
        console.log("WS failed -> fallback to polling");
        startPolling();
        socket.close();
      };

      socket.onclose = () => {
        clearSocketTimeout();
        if (socketRef.current === socket) {
          socketRef.current = null;
        }

        if (!shouldReconnect) {
          stopPolling();
          setConnectionState("closed");
          return;
        }

        startPolling();
        scheduleReconnect();
      };
    }

    connect();

    return () => {
      isMounted = false;
      shouldReconnect = false;
      clearSocketTimeout();
      stopPolling();

      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      if (pulseTimerRef.current) {
        window.clearTimeout(pulseTimerRef.current);
      }

      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  const data = selectChannelPayload(snapshot, channel, babyId);
  return { data, connectionState, lastUpdatedAt, hasFreshUpdate };
}
