let context: AudioContext | null = null;

export function unlockSound() {
  context ??= new AudioContext();
  void context.resume();
  speechSynthesis.speak(new SpeechSynthesisUtterance(""));
}

export function beep() {
  if (!context) return;
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.type = "square";
  oscillator.frequency.value = 880;
  gain.gain.value = 0.15;
  oscillator.connect(gain).connect(context.destination);
  oscillator.start();
  oscillator.stop(context.currentTime + 0.18);
}

export function say(text: string, clip = "") {
  if (clip) {
    void new Audio(`/voice/${clip}`).play().catch(() => speak(text));
    return;
  }
  speak(text);
}

function speak(text: string) {
  speechSynthesis.cancel();
  speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}
