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
  const [connectionState, setConnectionState] = useState("connecting");
  const [snapshot, setSnapshot] = useState(null);

  useEffect(() => {
    let shouldReconnect = true;

    async function loadInitialSnapshot() {
      try {
        const overview = await fetchOverview();
        setSnapshot(overview);
      } catch (error) {
        console.error("Failed to fetch initial overview", error);
      }
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
          setSnapshot(JSON.parse(event.data));
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

    loadInitialSnapshot();
    connect();

    return () => {
      shouldReconnect = false;

      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }

      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, []);

  const data = selectChannelPayload(snapshot, channel, babyId);
  return { data, connectionState };
}
