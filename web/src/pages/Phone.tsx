import { useEffect, useState } from "react";
import { Icon } from "../components/Icon";
import { useLive } from "../live";
import { beep, say, unlockSound } from "../sound";
import type { Status } from "../types";

const canVibrate = "vibrate" in navigator;
const STOP_PATTERN = [300, 100, 300];
const CLEAR_AFTER_MS = 6000;

type Message = { tone: "stop" | "clear" | "hold"; title: string };

export function Phone(_: { status: Status | null }) {
  const [armed, setArmed] = useState(false);
  const [message, setMessage] = useState<Message | null>(null);

  function show(next: Message, pattern: number | number[], spoken: string, clip = "") {
    navigator.vibrate?.(pattern);
    if (next.tone !== "clear") beep();
    say(spoken, clip);
    setMessage(next);
  }

  const live = useLive({
    onAlert: (alert) => {
      if (armed) show({ tone: "stop", title: alert.text }, STOP_PATTERN, alert.text, alert.clip);
    },
    onVerdict: (verdict) => {
      if (!armed) return;
      if (verdict.status === "cleared" && verdict.reason === "out_of_sequence") {
        show({ tone: "clear", title: "Carry on" }, 120, "Cleared. Carry on.");
      } else if (verdict.status === "confirmed" && verdict.reason === "step_check") {
        const text = verdict.spoken ?? "Stop. Check this step.";
        show({ tone: "stop", title: text }, STOP_PATTERN, text);
      } else if (verdict.status === "uncertain" && verdict.reason === "out_of_sequence") {
        show({ tone: "hold", title: "Hold. Call your supervisor." }, [200, 100, 200, 100, 200], "Hold. Call your supervisor.");
      }
    },
  });

  const held = live.state?.held ?? false;

  useEffect(() => {
    if (!message || held) return;
    const timer = setTimeout(() => setMessage(null), CLEAR_AFTER_MS);
    return () => clearTimeout(timer);
  }, [message, held]);

  function arm() {
    // Phones only allow sound and vibration after a tap.
    unlockSound();
    navigator.vibrate?.(60);
    setArmed(true);
  }

  function test() {
    show({ tone: "stop", title: "This is a test alert" }, STOP_PATTERN, "This is a test alert.");
    setTimeout(() => setMessage(null), 2500);
  }

  if (message) {
    return (
      <main className={`phone-alert ${message.tone}`} role="alert">
        <Icon name={message.tone === "clear" ? "check" : "stop"} size={72} />
        <p>{message.title}</p>
      </main>
    );
  }

  if (!armed) {
    return (
      <main className="page phone">
        <section className="card phone-card">
          <span className="phone-icon">
            <Icon name="bell" size={30} />
          </span>
          <h1>Get alerts on this phone</h1>
          <p>Vigil will speak and vibrate here the moment a step goes wrong, so the operator never has to look away.</p>
          <button className="primary" onClick={arm}>
            Turn on alerts
          </button>
          {!canVibrate && <p className="muted note">This browser cannot vibrate, so you will get sound only. Use Chrome on Android for vibration.</p>}
        </section>
      </main>
    );
  }

  return (
    <main className="page phone">
      <section className="card phone-card">
        <span className="phone-icon on">
          <Icon name="check" size={30} />
        </span>
        <h1>Alerts are on</h1>
        <p>Keep this screen open with the volume up.</p>
        <p className={`phone-link ${live.connected ? "good" : "bad"}`}>
          <span className={`dot ${live.connected ? "good" : "bad"}`} />
          {live.connected ? "Connected to Vigil" : "Reconnecting to Vigil"}
        </p>
        <button className="ghost" onClick={test}>
          Send a test alert
        </button>
      </section>
    </main>
  );
}
