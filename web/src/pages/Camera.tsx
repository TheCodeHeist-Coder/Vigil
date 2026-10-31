import { useEffect, useRef, useState } from "react";
import { post } from "../api";

const RETRY_MS = 1500;

export function Camera() {
  const video = useRef<HTMLVideoElement>(null);
  const peer = useRef<RTCPeerConnection | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const stopped = useRef(true);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [device, setDevice] = useState("");
  const [state, setState] = useState("not started");

  useEffect(() => () => stop(), []);

  async function connect() {
    if (stopped.current || !stream.current) return;
    const pc = new RTCPeerConnection({ iceServers: [] });
    peer.current = pc;
    stream.current.getVideoTracks().forEach((track) => {
      track.contentHint = "detail"; // keep resolution, and drop frame rate first if the link is slow
      pc.addTrack(track, stream.current!);
    });
    pc.onconnectionstatechange = () => {
      setState(pc.connectionState);
      if (pc.connectionState === "failed" || pc.connectionState === "disconnected") {
        pc.close();
        setTimeout(connect, RETRY_MS);
      }
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
      setState("ingest not reachable, retrying");
      pc.close();
      setTimeout(connect, RETRY_MS);
    }
  }

  async function start() {
    if (!navigator.mediaDevices) {
      setState("Camera needs HTTPS. Open this page with https:// and accept the certificate.");
      return;
    }
    stopped.current = false;
    stream.current = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 }, deviceId: device ? { exact: device } : undefined, facingMode: device ? undefined : "environment" },
      audio: false,
    });
    video.current!.srcObject = stream.current;
    setDevices((await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput"));
    await connect();
  }

  function stop() {
    stopped.current = true;
    peer.current?.close();
    stream.current?.getTracks().forEach((track) => track.stop());
    setState("stopped");
  }

  return (
    <main className="camera">
      <h1>Bench camera</h1>
      <video ref={video} autoPlay playsInline muted />
      <p className="state">Link: {state}</p>
      <div className="row">
        {devices.length > 1 && (
          <select value={device} onChange={(e) => setDevice(e.target.value)} aria-label="Camera">
            <option value="">Default camera</option>
            {devices.map((d) => (
              <option key={d.deviceId} value={d.deviceId}>
                {d.label || d.deviceId.slice(0, 8)}
              </option>
            ))}
          </select>
        )}
        <button onClick={start}>Start streaming</button>
        <button className="ghost" onClick={stop}>
          Stop
        </button>
      </div>
      <p className="hint">Frame the whole bench and the operator's shoulders, from high in front at about 45 degrees.</p>
    </main>
  );
}
