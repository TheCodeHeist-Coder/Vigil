import { useEffect, useRef, useState } from "react";
import { startCamera, stopCamera, useCamera } from "../camera";
import { Icon } from "../components/Icon";
import type { Status } from "../types";

export function Camera(_: { status: Status | null }) {
  const video = useRef<HTMLVideoElement>(null);
  const [device, setDevice] = useState("");
  const { link, size, devices, stream } = useCamera();

  useEffect(() => {
    if (video.current) video.current.srcObject = stream;
  }, [stream]);

  const streaming = link.tone === "live" || link.tone === "busy";

  return (
    <main className="page camera">
      <header className="page-head">
        <h1>Connect the bench camera</h1>
        <p>Open this page on the device that can see the bench. The camera keeps running when you switch pages.</p>
      </header>

      <div className="camera-grid">
        <div className="camera-view">
          <video ref={video} autoPlay playsInline muted />
          {!streaming && (
            <div className="stage-empty">
              <Icon name="camera" size={34} />
              <b>Camera preview</b>
              <p>Your video appears here once it starts.</p>
            </div>
          )}
        </div>

        <section className="card camera-panel">
          <div className={`link-state ${link.tone}`}>
            <span className="dot-large" />
            <div>
              <b>{link.label}</b>
              {link.detail && <small>{link.detail}</small>}
              {link.tone === "live" && size && <small>{size}</small>}
            </div>
          </div>

          {devices.length > 1 && (
            <label className="field">
              <span>Camera</span>
              <select value={device} onChange={(e) => setDevice(e.target.value)}>
                <option value="">Default camera</option>
                {devices.map((d) => (
                  <option key={d.deviceId} value={d.deviceId}>
                    {d.label || `Camera ${d.deviceId.slice(0, 6)}`}
                  </option>
                ))}
              </select>
            </label>
          )}

          {streaming ? (
            <button className="ghost" onClick={stopCamera}>
              Stop streaming
            </button>
          ) : (
            <button className="primary" onClick={() => void startCamera(device)}>
              Start camera
            </button>
          )}

          <div className="tips">
            <h2>Get the best view</h2>
            <ul>
              <li>Hold the phone sideways, so the video is wide.</li>
              <li>Place the camera high and in front, at about 45 degrees.</li>
              <li>Show the whole bench and the operator's shoulders.</li>
              <li>Keep it still, and keep the bench well lit.</li>
            </ul>
          </div>

          {link.tone === "live" && (
            <a className="link" href="#/">
              Go to Bench <Icon name="arrow" size={15} />
            </a>
          )}
        </section>
      </div>
    </main>
  );
}
