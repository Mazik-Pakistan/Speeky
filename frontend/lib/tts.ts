import { synthesizeSpeech } from "./conversation";

/** Speak `text` via the server's Piper voice, falling back to the browser's
 * native speech synthesis if the server TTS is unavailable (see backend
 * lib/tts_client.py). Resolves once playback ends (or fails). */
export async function playText(text: string): Promise<void> {
  try {
    const blob = await synthesizeSpeech(text);
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    await new Promise<void>((resolve) => {
      audio.onended = () => resolve();
      audio.onerror = () => resolve();
      audio.play().catch(() => resolve());
    });
    URL.revokeObjectURL(url);
  } catch {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    await new Promise<void>((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.onend = () => resolve();
      utterance.onerror = () => resolve();
      window.speechSynthesis.speak(utterance);
    });
  }
}
