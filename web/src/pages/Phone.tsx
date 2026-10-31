import { useState } from "react";
import { useLive } from "../live";
import { beep, say, unlockSound } from "../sound";

const canVibrate = "vibrate" in navigator;

export function Phone() {
  const [armed, setArmed] = useState(false);
  const [message, setMessage] = useState("Listening");
  const [tone, setTone] = useState("");

  useLive({
    onAlert: (alert) => {
      if (!armed) return;
      navigator.vibrate?.([300, 100, 300]);
      beep();
      say(alert.text, alert.clip);
      setMessage(alert.text);
      setTone("stop");
    },
    onVerdict: (verdict) => {
      if (!armed) return;
      if (verdict.status === "cleared" && verdict.reason === "out_of_sequence") {
        navigator.vibrate?.(120);
        say("Cleared. Carry on.");
        setMessage("Cleared. Carry on.");
        setTone("clear");
      } else if (verdict.status === "confirmed" && verdict.reason === "step_check") {
        navigator.vibrate?.([300, 100, 300]);
        beep();
        say(verdict.spoken ?? "Stop. Check this step.");
        setMessage(verdict.spoken ?? "Stop. Check this step.");
        setTone("stop");
      } else if (verdict.status === "uncertain" && verdict.reason === "out_of_sequence") {
        navigator.vibrate?.([200, 100, 200, 100, 200]);
        say("Hold. Call your supervisor.");
        setMessage("Hold. Call your supervisor.");
        setTone("stop");
      }
    },
  });

  function arm() {
    // Phones only allow sound and vibration after a tap.
    unlockSound();
    navigator.vibrate?.(60);
    setArmed(true);
  }

  if (!armed) {
    return (
      <main className="phone">
        <button className="arm" onClick={arm}>
          Tap to arm
        </button>
        {!canVibrate && <p>This browser cannot vibrate. Use Chrome on Android.</p>}
      </main>
    );
  }
  return (
    <main className={`phone ${tone}`}>
      <p className="message">{message}</p>
    </main>
  );
}
