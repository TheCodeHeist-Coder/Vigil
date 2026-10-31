import { useEffect, useRef, useState } from "react";
import { health } from "../status";
import type { Status } from "../types";
import { Icon, type IconName } from "./Icon";

export type Route = "" | "camera" | "phone" | "supervisor";

const LINKS: { route: Route; label: string; icon: IconName }[] = [
  { route: "", label: "Bench", icon: "bench" },
  { route: "camera", label: "Camera", icon: "camera" },
  { route: "phone", label: "Phone", icon: "phone" },
  { route: "supervisor", label: "Supervisor", icon: "supervisor" },
];

function Links({ page, className }: { page: Route; className: string }) {
  return (
    <nav className={className} aria-label="Main">
      {LINKS.map((link) => (
        <a key={link.route} href={`#/${link.route}`} className={page === link.route ? "on" : ""} aria-current={page === link.route ? "page" : undefined}>
          <Icon name={link.icon} />
          <span>{link.label}</span>
        </a>
      ))}
    </nav>
  );
}

function Row({ name, value, ok, hint }: { name: string; value: string; ok: boolean; hint?: string }) {
  return (
    <li>
      <span className={`dot ${ok ? "good" : "warn"}`} />
      <div>
        <b>{name}</b>
        <span>{value}</span>
        {hint && <small>{hint}</small>}
      </div>
    </li>
  );
}

function StatusMenu({ status }: { status: Status | null }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const summary = health(status);

  useEffect(() => {
    if (!open) return;
    const onPress = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    addEventListener("mousedown", onPress);
    addEventListener("keydown", onKey);
    return () => {
      removeEventListener("mousedown", onPress);
      removeEventListener("keydown", onKey);
    };
  }, [open]);

  const ai = status?.model !== "local-rules";
  const meko = status?.meko.state === "connected";

  return (
    <div className="status-menu" ref={root}>
      <button className={`status-button ${summary.tone}`} onClick={() => setOpen(!open)} aria-expanded={open} aria-haspopup="true">
        <span className={`dot ${summary.tone}`} />
        {summary.label}
        <Icon name="chevron" size={16} />
      </button>
      {open && (
        <div className="status-panel" role="dialog" aria-label="System status">
          <h2>System status</h2>
          {!status ? (
            <p className="muted">Vigil cannot reach its services. Run ./dev.sh on the bench laptop.</p>
          ) : (
            <ul>
              <Row name="Camera" value={status.camera_live ? "Live" : "Not connected"} ok={status.camera_live} hint={status.camera_live ? undefined : "Open the Camera page on the device watching the bench."} />
              <Row name="AI checks" value={ai ? "Gemini" : "Local rules only"} ok={ai} hint={ai ? undefined : "Photo checks are off until a Gemini key is set."} />
              <Row name="Agent memory" value={meko ? "Meko" : "YugabyteDB"} ok={meko} hint={meko ? undefined : status.meko.detail} />
              <Row name="Database" value={status.database === "connected" ? "Connected" : "Offline"} ok={status.database === "connected"} />
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

export function AppBar({ page, status }: { page: Route; status: Status | null }) {
  return (
    <>
      <header className="appbar">
        <a className="brand" href="#/" aria-label="Vigil, go to Bench">
          <svg width="26" height="26" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinejoin="round" aria-hidden="true">
            <path d="M16 3.5 26.8 9.75v12.5L16 28.5 5.2 22.25V9.75Z" />
            <circle cx="16" cy="16" r="5" />
          </svg>
          <span>Vigil</span>
        </a>
        <Links page={page} className="navlinks" />
        <StatusMenu status={status} />
      </header>
      {status?.replay && <div className="replay-strip">Replay mode: decisions shown are saved from earlier runs, not live.</div>}
      <Links page={page} className="tabbar" />
    </>
  );
}
