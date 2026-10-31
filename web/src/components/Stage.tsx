import { useEffect, useRef, useState } from "react";
import { put } from "../api";
import type { HandTrack, Point, Zone } from "../types";

type Props = { zones: Zone[]; onZones: (z: Zone[]) => void; track: HandTrack | null; expectedBin: string | null };

const ACTIVE = "#3ddc97";
const QUIET = "rgba(255,255,255,.55)";

export function Stage({ zones, onZones, track, expectedBin }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [drag, setDrag] = useState<{ start: Point; end: Point } | null>(null);

  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const box = element.getBoundingClientRect();
    element.width = box.width;
    element.height = box.height;
    const c = element.getContext("2d")!;
    const X = (p: Point): Point => [p[0] * box.width, p[1] * box.height];

    for (const zone of zones) {
      const on = zone.id === expectedBin;
      c.beginPath();
      zone.polygon.forEach((point, i) => (i ? c.lineTo(...X(point)) : c.moveTo(...X(point))));
      c.closePath();
      c.lineWidth = on ? 4 : 2;
      c.strokeStyle = on ? ACTIVE : QUIET;
      c.stroke();
      if (on) {
        c.fillStyle = "rgba(61,220,151,.16)";
        c.fill();
      }
      const [x, y] = X(zone.polygon[0]);
      c.font = "600 16px system-ui";
      c.fillStyle = on ? ACTIVE : "#fff";
      c.fillText(zone.label, x + 8, y + 22);
    }

    for (const point of track?.skeleton ?? []) {
      const [x, y] = X(point);
      c.beginPath();
      c.arc(x, y, 5, 0, 7);
      c.fillStyle = "rgba(255,255,255,.7)";
      c.fill();
    }
    for (const point of track?.hands ?? []) {
      const [x, y] = X(point);
      c.beginPath();
      c.arc(x, y, 12, 0, 7);
      c.lineWidth = 4;
      c.strokeStyle = "#ffb020";
      c.stroke();
    }
    if (drag) {
      const [x1, y1] = X(drag.start);
      const [x2, y2] = X(drag.end);
      c.lineWidth = 3;
      c.strokeStyle = "#ffb020";
      c.strokeRect(x1, y1, x2 - x1, y2 - y1);
    }
  }, [zones, track, expectedBin, drag]);

  const point = (event: React.PointerEvent): Point => {
    const box = canvas.current!.getBoundingClientRect();
    return [(event.clientX - box.left) / box.width, (event.clientY - box.top) / box.height];
  };

  async function finish() {
    if (!drag || !editing) return;
    const [x1, y1] = drag.start;
    const [x2, y2] = drag.end;
    const polygon: Point[] = [
      [Math.min(x1, x2), Math.min(y1, y2)],
      [Math.max(x1, x2), Math.min(y1, y2)],
      [Math.max(x1, x2), Math.max(y1, y2)],
      [Math.min(x1, x2), Math.max(y1, y2)],
    ];
    const next = zones.map((zone) => (zone.id === editing ? { ...zone, polygon } : zone));
    setDrag(null);
    onZones(next);
    await put("/api/zones", next);
  }

  return (
    <div className="stage-wrap">
      <div className="stage">
        <img src="/video" alt="Live bench camera" />
        <canvas
          ref={canvas}
          className={editing ? "editing" : ""}
          onPointerDown={(e) => {
            if (!editing) return;
            const p = point(e);
            setDrag({ start: p, end: p });
          }}
          onPointerMove={(e) => drag && setDrag({ ...drag, end: point(e) })}
          onPointerUp={finish}
        />
        <span className="source">{track?.source ?? "no tracking"}</span>
      </div>
      <div className="zone-bar">
        <span>Draw zone:</span>
        {zones.map((zone) => (
          <button key={zone.id} className={editing === zone.id ? "on" : ""} onClick={() => setEditing(editing === zone.id ? null : zone.id)}>
            {zone.id}
          </button>
        ))}
      </div>
    </div>
  );
}
