"use client";

/**
 * A plain self-view camera: getUserMedia, an element to attach it to, and a stop on the way out.
 *
 * Deliberately unrelated to lib/vision/useVideoAnalysis — that one loads MediaPipe and feeds the
 * delivery scorer. This is for phases where the user should see themselves but nothing is being
 * measured (Public Speaking's Q&A), so it carries none of that cost and its frames go nowhere.
 */

import * as React from "react";

export interface UseSelfCameraResult {
  videoRef: React.RefObject<HTMLVideoElement>;
  error: string | null;
}

export function useSelfCamera(enabled: boolean): UseSelfCameraResult {
  const videoRef = React.useRef<HTMLVideoElement>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!enabled) return;

    let stream: MediaStream | null = null;
    let cancelled = false;

    // Undefined rather than a rejected promise when the page is not on localhost or HTTPS —
    // a bare `.getUserMedia` call would throw a TypeError that reads like a bug in this hook.
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera needs a secure page (localhost or HTTPS).");
      return;
    }

    setError(null);
    navigator.mediaDevices
      .getUserMedia({ video: true, audio: false })
      .then((result) => {
        // The room is what owns the microphone; a second audio capture here would double it.
        if (cancelled) {
          result.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = result;
        const video = videoRef.current;
        if (!video) return;
        video.srcObject = result;
        void video.play();
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? `Camera unavailable: ${err.message}` : "Camera unavailable");
        }
      });

    return () => {
      cancelled = true;
      // A camera indicator left on after the panel closes reads as a privacy breach, so release
      // the device rather than just detaching the element.
      stream?.getTracks().forEach((track) => track.stop());
      if (videoRef.current) videoRef.current.srcObject = null;
    };
  }, [enabled]);

  return { videoRef, error };
}
