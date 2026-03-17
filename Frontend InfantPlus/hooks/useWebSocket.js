import { useEffect, useRef, useState } from "react";
import { fetchOverview } from "../services/api";
import { createNICUSocket } from "../services/socket";

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

export function useWebSocket({ channel = "overview", babyId } = {}) {
  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const pollingTimerRef = useRef(null);
  const pulseTimerRef = useRef(null);
  const [connectionState, setConnectionState] = useState("connecting");
  const [snapshot, setSnapshot] = useState(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
  const [hasFreshUpdate, setHasFreshUpdate] = useState(false);

  useEffect(() => {
    let shouldReconnect = true;

    function applySnapshot(nextSnapshot) {
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

    function startPolling() {
      pollingTimerRef.current = window.setInterval(() => {
        loadSnapshot();
      }, 2000);
    }

    function connect() {
      const socket = createNICUSocket();
      socketRef.current = socket;
      setConnectionState("connecting");

      socket.onopen = () => {
        setConnectionState("open");
      };

      socket.onmessage = (event) => {
        try {
          applySnapshot(JSON.parse(event.data));
        } catch (error) {
          console.error("Failed to parse WebSocket payload", error);
        }
      };

      socket.onerror = () => {
        socket.close();
      };

      socket.onclose = () => {
        if (!shouldReconnect) {
          setConnectionState("closed");
          return;
        }

        setConnectionState("reconnecting");
        reconnectTimerRef.current = window.setTimeout(() => {
          connect();
        }, 1200);
      };
    }

    loadSnapshot();
    startPolling();
    connect();

    return () => {
      shouldReconnect = false;

      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }

      if (pollingTimerRef.current) {
        window.clearInterval(pollingTimerRef.current);
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
