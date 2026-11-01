import { useEffect, useRef, useState } from "react";
import { put } from "../api";
import type { HandTrack, Point, Zone } from "../types";
import { Icon } from "./Icon";

type Props = {
  zones: Zone[];
  onZones: (z: Zone[]) => void;
  track: HandTrack | null;
  targetBin: string | null;
  cameraLive: boolean;
  setup: boolean;
  onSetup: (on: boolean) => void;
};

const TARGET = "#22c58b";
const FRAME_GAP_MS = 80; // at most about 12 frames a second
const RETRY_MS = 500;

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const QUIET = "rgba(255,255,255,.7)";

export function Stage({ zones, onZones, track, targetBin, cameraLive, setup, onSetup }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const video = useRef<HTMLImageElement>(null);
  const [ratio, setRatio] = useState(16 / 9);
  const [index, setIndex] = useState(0);
  const [drag, setDrag] = useState<{ start: Point; end: Point } | null>(null);

  const current = setup ? zones[index] : null;

  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const box = element.getBoundingClientRect();
    const ratio = devicePixelRatio || 1;
    element.width = box.width * ratio;
    element.height = box.height * ratio;
    const c = element.getContext("2d")!;
    c.scale(ratio, ratio);
    const X = (p: Point): Point => [p[0] * box.width, p[1] * box.height];

    // Boxes mean nothing without the bench behind them.
    for (const zone of cameraLive ? zones : []) {
      const on = zone.id === targetBin || zone.id === current?.id;
      const [x, y] = X(zone.polygon[0]);
      c.beginPath();
      zone.polygon.forEach((point, i) => (i ? c.lineTo(...X(point)) : c.moveTo(...X(point))));
      c.closePath();
      c.lineWidth = on ? 3.5 : 1.5;
      c.strokeStyle = on ? TARGET : QUIET;
      c.setLineDash(on ? [] : [6, 5]);
      c.stroke();
      c.setLineDash([]);
      if (on) {
        c.fillStyle = "rgba(34,197,139,.18)";
        c.fill();
      }
      const small = box.width < 620;
      const label = small ? zone.label.split(" · ")[0] : zone.label;
      c.font = `600 ${small ? 10.5 : 13}px 'Inter Variable', system-ui`;
      const width = c.measureText(label).width + 14;
      c.fillStyle = on ? TARGET : "rgba(16,24,40,.72)";
      c.beginPath();
      c.roundRect(x + 6, y + 6, width, 22, 6);
      c.fill();
      c.fillStyle = on ? "#06281c" : "#fff";
      c.fillText(label, x + 13, y + 22);
    }

    for (const point of track?.hands ?? []) {
      const [x, y] = X(point);
      c.beginPath();
      c.arc(x, y, 11, 0, 7);
      c.lineWidth = 3.5;
      c.strokeStyle = "#ffb020";
      c.stroke();
    }
    if (drag) {
      const [x1, y1] = X(drag.start);
      const [x2, y2] = X(drag.end);
      c.lineWidth = 3;
      c.strokeStyle = TARGET;
      c.fillStyle = "rgba(34,197,139,.18)";
      c.fillRect(x1, y1, x2 - x1, y2 - y1);
      c.strokeRect(x1, y1, x2 - x1, y2 - y1);
    }
  }, [zones, track, targetBin, drag, current, cameraLive, ratio]);

  useEffect(() => setIndex(0), [setup]);

  // Asks for the next frame only after showing the last, so delay can never build up.
  useEffect(() => {
    if (!cameraLive) return;
    let alive = true;
    let shown = "";
    (async () => {
      while (alive) {
        const started = performance.now();
        try {
          const response = await fetch("/frame.jpg", { cache: "no-store" });
          if (response.status === 200 && video.current) {
            const url = URL.createObjectURL(await response.blob());
            video.current.src = url;
            if (shown) URL.revokeObjectURL(shown);
            shown = url;
          } else {
            await wait(RETRY_MS);
          }
        } catch {
          await wait(RETRY_MS);
        }
        await wait(Math.max(0, FRAME_GAP_MS - (performance.now() - started)));
      }
    })();
    return () => {
      alive = false;
      if (shown) URL.revokeObjectURL(shown);
    };
  }, [cameraLive]);

  function onFrame(event: React.SyntheticEvent<HTMLImageElement>) {
    const { naturalWidth, naturalHeight } = event.currentTarget;
    if (naturalWidth && naturalHeight) setRatio(naturalWidth / naturalHeight);
  }

  const point = (event: React.PointerEvent): Point => {
    const box = canvas.current!.getBoundingClientRect();
    const clamp = (n: number) => Math.min(1, Math.max(0, n));
    return [clamp((event.clientX - box.left) / box.width), clamp((event.clientY - box.top) / box.height)];
  };

  function finishSetup() {
    try {
      localStorage.setItem("vigil.zones", "done");
    } catch {
      // the checklist tick is only a convenience
    }
    onSetup(false);
  }

  function advance() {
    if (index + 1 >= zones.length) finishSetup();
    else setIndex(index + 1);
  }

  async function finish() {
    if (!drag || !current) return;
    const [x1, y1] = drag.start;
    const [x2, y2] = drag.end;
    setDrag(null);
    if (Math.abs(x2 - x1) < 0.02 || Math.abs(y2 - y1) < 0.02) return; // a stray click, not a box
    const polygon: Point[] = [
      [Math.min(x1, x2), Math.min(y1, y2)],
      [Math.max(x1, x2), Math.min(y1, y2)],
      [Math.max(x1, x2), Math.max(y1, y2)],
      [Math.min(x1, x2), Math.max(y1, y2)],
    ];
    const next = zones.map((zone) => (zone.id === current.id ? { ...zone, polygon } : zone));
    onZones(next);
    await put("/api/zones", next);
    advance();
  }

  return (
    <div className="stage-wrap">
    <div className="stage" style={{ aspectRatio: ratio, maxWidth: `calc(72vh * ${ratio})` }}>
      {cameraLive ? <img ref={video} onLoad={onFrame} alt="Live view of the bench" /> : <div className="stage-blank" />}
      <canvas
        ref={canvas}
        className={setup ? "drawing" : ""}
        onPointerDown={(e) => {
          if (!setup) return;
          const p = point(e);
          setDrag({ start: p, end: p });
        }}
        onPointerMove={(e) => drag && setDrag({ ...drag, end: point(e) })}
        onPointerUp={finish}
      />

      {!cameraLive && !setup && (
        <div className="stage-empty">
          <Icon name="camera" size={34} />
          <b>No camera connected</b>
          <p>Open the Camera page on the device watching the bench.</p>
          <a className="button" href="#/camera">
            Open Camera
          </a>
        </div>
      )}

      {cameraLive && !setup && (
        <span className={`live-tag ${track?.hands.length ? "tracking" : ""}`}>{track?.hands.length ? "Hands tracked" : "Live"}</span>
      )}
    </div>
    {setup && current && (
        <div className="setup-bar">
          <div>
            <span className="eyebrow">
              Mark zone {index + 1} of {zones.length}
            </span>
            <b>Drag a box around {current.label}</b>
          </div>
          <button className="ghost" onClick={advance}>
            Keep this one
          </button>
          <button onClick={finishSetup}>Done</button>
        </div>
      )}
    </div>
  );
}
