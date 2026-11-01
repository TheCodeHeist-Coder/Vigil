import { useSyncExternalStore } from "react";
import { post } from "./api";

export type Link = { tone: "idle" | "busy" | "live" | "bad"; label: string; detail?: string };

type Camera = { link: Link; size: string; devices: MediaDeviceInfo[]; stream: MediaStream | null };

const RETRY_MS = 1500;
const FRAME_RATE = 15; // hand tracking runs near this, so more would only waste bitrate

// Chrome starts low and rarely climbs on a phone link, which shrank real video to 180p.
// A floor keeps it big enough to find hands and to read the notch labels.
const START_KBPS = 1200;
const MIN_KBPS = 600;
const MAX_KBPS = 2500;
const IDLE: Link = { tone: "idle", label: "Not streaming" };

// The camera lives here, outside any page, so moving between pages never stops it.
let camera: Camera = { link: IDLE, size: "", devices: [], stream: null };
let peer: RTCPeerConnection | null = null;
let stopped = true;
let screenLock: WakeLockSentinel | null = null;
const listeners = new Set<() => void>();

function update(change: Partial<Camera>) {
  camera = { ...camera, ...change };
  listeners.forEach((listener) => listener());
}

// A phone that locks its screen stops the camera, so stay awake while streaming.
async function keepScreenOn() {
  try {
    screenLock = (await navigator.wakeLock?.request("screen")) ?? null;
  } catch {
    screenLock = null; // battery saver can refuse this, and the video still works
  }
}

// The browser drops the lock whenever the page is hidden, so take it again on return.
document.addEventListener("visibilitychange", () => {
  if (!stopped && document.visibilityState === "visible") void keepScreenOn();
});

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function withBitrateFloor(sdp: string): string {
  const settings = `x-google-start-bitrate=${START_KBPS};x-google-min-bitrate=${MIN_KBPS};x-google-max-bitrate=${MAX_KBPS}`;
  const codecs = [...sdp.matchAll(/^a=rtpmap:(\d+) (?:VP8|H264)\/90000/gm)].map((match) => match[1]);
  return codecs.reduce((text, payload) => {
    const parameters = new RegExp(`^a=fmtp:${payload} (.*)$`, "m");
    if (parameters.test(text)) return text.replace(parameters, `a=fmtp:${payload} $1;${settings}`);
    return text.replace(new RegExp(`^(a=rtpmap:${payload} .*)$`, "m"), `$1\r\na=fmtp:${payload} ${settings}`);
  }, sdp);
}

function cameraError(error: unknown): Link {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError") return { tone: "bad", label: "Camera blocked", detail: "Allow the camera in your browser's site settings, then try again." };
  if (name === "NotFoundError") return { tone: "bad", label: "No camera found", detail: "Connect a camera to this device, then try again." };
  if (name === "NotReadableError") return { tone: "bad", label: "Camera in use", detail: "Close any other app using the camera, then try again." };
  return { tone: "bad", label: "Camera failed to start", detail: "Try again, or choose another camera." };
}

async function connect() {
  const stream = camera.stream;
  if (stopped || !stream) return;
  const pc = new RTCPeerConnection({ iceServers: [] });
  peer = pc;
  stream.getVideoTracks().forEach((track) => {
    // Protecting resolution dropped a real phone to 1 fps, which is too few frames
    // to see a hand enter a bin, so motion comes first and the bitrate floor protects size.
    track.contentHint = "motion";
    pc.addTrack(track, stream);
  });
  const retry = () => {
    pc.close();
    if (stopped) return;
    update({ link: { tone: "busy", label: "Reconnecting", detail: "Vigil lost the video link and is trying again." } });
    setTimeout(connect, RETRY_MS);
  };
  pc.onconnectionstatechange = () => {
    if (pc.connectionState === "connected") update({ link: { tone: "live", label: "Streaming to Vigil" } });
    if (pc.connectionState === "failed" || pc.connectionState === "disconnected") retry();
  };

  await pc.setLocalDescription(await pc.createOffer());
  await new Promise<void>((resolve) => {
    if (pc.iceGatheringState === "complete") return resolve();
    pc.onicegatheringstatechange = () => pc.iceGatheringState === "complete" && resolve();
  });

  try {
    const answer = await post<RTCSessionDescriptionInit>("/webrtc/offer", { sdp: pc.localDescription!.sdp, type: pc.localDescription!.type });
    await pc.setRemoteDescription({ type: answer.type, sdp: withBitrateFloor(answer.sdp ?? "") });
  } catch {
    retry();
  }
}

export async function startCamera(device: string) {
  if (!navigator.mediaDevices) {
    update({ link: { tone: "bad", label: "Secure link needed", detail: "On this laptop use http://localhost:5173. On a phone use the https address on port 5174." } });
    return;
  }
  update({ link: { tone: "busy", label: "Connecting" } });
  stopped = false;
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: FRAME_RATE }, deviceId: device ? { exact: device } : undefined, facingMode: device ? undefined : "environment" },
      audio: false,
    });
  } catch (error) {
    stopped = true;
    update({ link: cameraError(error) });
    return;
  }
  const settings = stream.getVideoTracks()[0].getSettings();
  const devices = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
  update({ stream, devices, size: settings.width ? `${settings.width} × ${settings.height}` : "" });
  void keepScreenOn();
  await connect();
}

export function stopCamera() {
  stopped = true;
  peer?.close();
  camera.stream?.getTracks().forEach((track) => track.stop());
  void screenLock?.release();
  screenLock = null;
  update({ stream: null, size: "", link: IDLE });
}

export function useCamera(): Camera {
  return useSyncExternalStore(subscribe, () => camera);
}
