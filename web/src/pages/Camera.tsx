import { useEffect, useRef, useState } from "react";
import { post } from "../api";
import { Icon } from "../components/Icon";
import type { Status } from "../types";

const RETRY_MS = 1500;

type Link = { tone: "idle" | "busy" | "live" | "bad"; label: string; detail?: string };

const IDLE: Link = { tone: "idle", label: "Not streaming" };

function cameraError(error: unknown): Link {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError") return { tone: "bad", label: "Camera blocked", detail: "Allow the camera in your browser's site settings, then try again." };
  if (name === "NotFoundError") return { tone: "bad", label: "No camera found", detail: "Connect a camera to this device, then try again." };
  if (name === "NotReadableError") return { tone: "bad", label: "Camera in use", detail: "Close any other app using the camera, then try again." };
  return { tone: "bad", label: "Camera failed to start", detail: "Try again, or choose another camera." };
}

export function Camera(_: { status: Status | null }) {
  const video = useRef<HTMLVideoElement>(null);
  const peer = useRef<RTCPeerConnection | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const stopped = useRef(true);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [device, setDevice] = useState("");
  const [link, setLink] = useState<Link>(IDLE);
  const [size, setSize] = useState("");

  useEffect(() => () => stop(), []);

  async function connect() {
    if (stopped.current || !stream.current) return;
    const pc = new RTCPeerConnection({ iceServers: [] });
    peer.current = pc;
    stream.current.getVideoTracks().forEach((track) => {
      track.contentHint = "detail"; // keep resolution, and drop frame rate first if the link is slow
      pc.addTrack(track, stream.current!);
    });
    const retry = () => {
      pc.close();
      if (stopped.current) return;
      setLink({ tone: "busy", label: "Reconnecting", detail: "Vigil lost the video link and is trying again." });
      setTimeout(connect, RETRY_MS);
    };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "connected") setLink({ tone: "live", label: "Streaming to Vigil" });
      if (pc.connectionState === "failed" || pc.connectionState === "disconnected") retry();
    };

    await pc.setLocalDescription(await pc.createOffer());
    await new Promise<void>((resolve) => {
      if (pc.iceGatheringState === "complete") return resolve();
      pc.onicegatheringstatechange = () => pc.iceGatheringState === "complete" && resolve();
    });

    try {
      const answer = await post<RTCSessionDescriptionInit>("/webrtc/offer", { sdp: pc.localDescription!.sdp, type: pc.localDescription!.type });
      await pc.setRemoteDescription(answer);
    } catch {
      retry();
    }
  }

  async function start() {
    if (!navigator.mediaDevices) {
      setLink({ tone: "bad", label: "Secure link needed", detail: "Open this page with https:// and accept the certificate warning." });
      return;
    }
    setLink({ tone: "busy", label: "Connecting" });
    stopped.current = false;
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 }, deviceId: device ? { exact: device } : undefined, facingMode: device ? undefined : "environment" },
        audio: false,
      });
    } catch (error) {
      stopped.current = true;
      setLink(cameraError(error));
      return;
    }
    const settings = stream.current.getVideoTracks()[0].getSettings();
    setSize(settings.width ? `${settings.width} × ${settings.height}` : "");
    video.current!.srcObject = stream.current;
    setDevices((await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput"));
    await connect();
  }

  function stop() {
    stopped.current = true;
    peer.current?.close();
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    if (video.current) video.current.srcObject = null;
    setLink(IDLE);
    setSize("");
  }

  const streaming = link.tone === "live" || link.tone === "busy";

  return (
    <main className="page camera">
      <header className="page-head">
        <h1>Connect the bench camera</h1>
        <p>Open this page on the device that can see the bench.</p>
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
            <button className="ghost" onClick={stop}>
              Stop streaming
            </button>
          ) : (
            <button className="primary" onClick={start}>
              Start camera
            </button>
          )}

          <div className="tips">
            <h2>Get the best view</h2>
            <ul>
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
