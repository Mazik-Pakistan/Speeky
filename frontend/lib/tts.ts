import { synthesizeSpeech } from "./conversation";

// Module-level, not per-component: every playText() call — from any button,
// any page — shares this, so only one clip is ever audible at a time. A
// `generation` counter invalidates in-flight calls too, not just the audio
// element, so a stale fetch that resolves after being superseded doesn't
// start playing a message that's no longer current.
let generation = 0;
let currentAudio: HTMLAudioElement | null = null;

export function stopCurrent() {
  generation += 1;
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.src = "";
    currentAudio = null;
  }
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

/** Speak `text` via the server's Piper voice, falling back to the browser's
 * native speech synthesis if the server TTS is unavailable (see backend
 * lib/tts_client.py). Stops any audio already playing first, so repeated
 * clicks or a burst of new messages never overlap. Resolves once playback
 * ends (or fails, or gets superseded by a newer call).
 *
 * `lengthScale` mirrors Piper's own knob: 1.0 normal speed, >1.0 slower — for a
 * second, easier-to-catch replay of the same line (e.g. the baseline assessment's
 * pronunciation questions). The browser fallback has no length_scale concept, so it
 * gets the inverse as `rate` (SpeechSynthesisUtterance: lower rate = slower). */
export async function playText(text: string, lengthScale = 1.0): Promise<void> {
  stopCurrent();
  const myGeneration = generation;

  try {
    const blob = await synthesizeSpeech(text, lengthScale);
    if (myGeneration !== generation) return; // superseded while fetching
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    currentAudio = audio;
    await new Promise<void>((resolve) => {
      audio.onended = () => resolve();
      audio.onerror = () => resolve();
      audio.play().catch(() => resolve());
    });
    URL.revokeObjectURL(url);
    if (currentAudio === audio) currentAudio = null;
  } catch {
    if (myGeneration !== generation) return;
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    await new Promise<void>((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1 / lengthScale;
      utterance.onend = () => resolve();
      utterance.onerror = () => resolve();
      window.speechSynthesis.speak(utterance);
    });
  }
}
