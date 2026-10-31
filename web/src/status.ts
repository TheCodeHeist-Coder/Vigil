import { useEffect, useState } from "react";
import { get } from "./api";
import type { Status } from "./types";

export type Health = { tone: "good" | "warn" | "bad" | "idle"; label: string };

export function useStatus(): Status | null {
  const [status, setStatus] = useState<Status | null>(null);

  useEffect(() => {
    const refresh = () => {
      get<Status>("/api/status")
        .then(setStatus)
        .catch(() => setStatus(null));
    };
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, []);

  return status;
}

export function health(status: Status | null): Health {
  if (!status) return { tone: "idle", label: "Connecting" };
  if (status.database !== "connected") return { tone: "bad", label: "Database offline" };
  if (status.replay) return { tone: "warn", label: "Replay mode" };
  if (status.model === "local-rules") return { tone: "warn", label: "AI offline" };
  if (!status.camera_live) return { tone: "warn", label: "Camera off" };
  return { tone: "good", label: "Ready" };
}
