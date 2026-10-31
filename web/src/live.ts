import { useEffect, useRef, useState } from "react";
import type { HandTrack, Incident, ReflexAlert, RunState, Verdict } from "./types";

export type Live = {
  connected: boolean;
  track: HandTrack | null;
  state: RunState | null;
  alert: ReflexAlert | null;
  alertMs: number | null;
  verdict: Verdict | null;
  incident: Incident | null;
  checks: Record<string, Verdict["status"]>; // photo check result per step
};

type Handlers = { onAlert?: (a: ReflexAlert) => void; onVerdict?: (v: Verdict) => void };

const empty: Live = { connected: false, track: null, state: null, alert: null, alertMs: null, verdict: null, incident: null, checks: {} };

export function useLive(handlers: Handlers = {}): Live {
  const [live, setLive] = useState<Live>(empty);
  const latest = useRef(handlers);
  latest.current = handlers;

  useEffect(() => {
    let socket: WebSocket;
    let closed = false;

    function connect() {
      const scheme = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${location.host}/ws/live`);
      socket.onopen = () => setLive((l) => ({ ...l, connected: true }));
      socket.onclose = () => {
        setLive((l) => ({ ...l, connected: false }));
        if (!closed) setTimeout(connect, 1000);
      };
      socket.onmessage = (event) => {
        const { topic, body } = JSON.parse(event.data);
        if (topic === "hand.tracks") setLive((l) => ({ ...l, track: body }));
        else if (topic === "run.ended") setLive((l) => ({ ...empty, connected: l.connected, track: l.track }));
        else if (topic === "run.state")
          setLive((l) => (l.state?.run_id === body.run_id ? { ...l, state: body } : { ...empty, connected: l.connected, track: l.track, state: body }));
        else if (topic === "alerts.reflex") {
          // Same laptop, same clock: this is frame received to alert on screen.
          const alertMs = Math.round(Date.now() - body.times.t_ingest * 1000);
          setLive((l) => ({ ...l, alert: body, alertMs, verdict: null, incident: null }));
          latest.current.onAlert?.(body);
        } else if (topic === "verdicts") {
          setLive((l) => ({
            ...l,
            verdict: body,
            checks: body.reason === "step_check" ? { ...l.checks, [body.step_id]: body.status } : l.checks,
          }));
          latest.current.onVerdict?.(body);
        } else if (topic === "incidents") setLive((l) => ({ ...l, incident: body }));
      };
    }

    connect();
    return () => {
      closed = true;
      socket.close();
    };
  }, []);

  return live;
}
