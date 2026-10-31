import { useState } from "react";
import { Icon } from "./Icon";

type Props = { cameraLive: boolean; onSetup: () => void; onStart: (serial: string, revision: "A" | "B") => void; suggested: string; returning: boolean };

const REVISIONS = [
  { id: "A", name: "Rev A", note: "Gasket fitted by hand" },
  { id: "B", name: "Rev B", note: "Gasket already fitted" },
] as const;

function zonesMarked(): boolean {
  try {
    return localStorage.getItem("vigil.zones") === "done";
  } catch {
    return false;
  }
}

export function StartCard({ cameraLive, onSetup, onStart, suggested, returning }: Props) {
  const zonesDone = zonesMarked();
  const [serial, setSerial] = useState(suggested);
  const [revision, setRevision] = useState<"A" | "B">("A");

  return (
    <section className="card start">
      {!returning && (
        <>
      <h2>Before you start</h2>
      <ul className="checklist">
        <li className={cameraLive ? "ok" : ""}>
          <span className="tick">{cameraLive && <Icon name="check" size={14} />}</span>
          <div>
            <b>Camera</b>
            <small>{cameraLive ? "Connected and live" : "Not connected yet"}</small>
          </div>
          {!cameraLive && (
            <a className="link" href="#/camera">
              Connect
            </a>
          )}
        </li>
        <li className={zonesDone ? "ok" : ""}>
          <span className="tick">{zonesDone && <Icon name="check" size={14} />}</span>
          <div>
            <b>Bench zones</b>
            <small>{zonesDone ? "Marked on the video" : "Mark each bin on the video"}</small>
          </div>
          <button className="link" onClick={onSetup}>
            {zonesDone ? "Change" : "Mark zones"}
          </button>
        </li>
        <li>
          <span className="tick" />
          <div>
            <b>Operator phone</b>
            <small>Optional, for voice and vibration</small>
          </div>
          <a className="link" href="#/phone">
            Set up
          </a>
        </li>
      </ul>
        </>
      )}

      <h2>{returning ? "Next unit" : "Unit details"}</h2>
      <label className="field">
        <span>Serial number</span>
        <input value={serial} onChange={(e) => setSerial(e.target.value)} />
      </label>
      <fieldset className="revisions">
        <legend>Revision</legend>
        {REVISIONS.map((option) => (
          <label key={option.id} className={revision === option.id ? "on" : ""}>
            <input type="radio" name="revision" checked={revision === option.id} onChange={() => setRevision(option.id)} />
            <b>{option.name}</b>
            <small>{option.note}</small>
          </label>
        ))}
      </fieldset>
      <button className="primary" disabled={!serial.trim()} onClick={() => onStart(serial.trim(), revision)}>
        Start assembly
      </button>
      {!cameraLive && <p className="muted note">Vigil cannot see the bench until the camera is connected.</p>}
    </section>
  );
}
