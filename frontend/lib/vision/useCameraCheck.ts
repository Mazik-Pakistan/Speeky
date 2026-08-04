"use client";

/**
 * Drives the three-step camera check: permission/device, framing, then the two calibration holds.
 *
 * This is where the ~16MB of wasm and models is downloaded, deliberately. Doing it here rather
 * than at `startVideo()` means the wait happens while the user is already looking at a modal
 * with a progress bar, instead of stalling the first seconds of their speech.
 *
 * The calibration itself is the point of the whole flow. Everything downstream — the aggregator,
 * the backend scorer, the results tile — treats an uncalibrated session as untrustworthy,
 * because with a webcam mounted above the screen there is no way to know what "looking at the
 * camera" means for a given user without measuring it.
 */

import * as React from "react";

import {
  calibrateFromTargets,
  type CalibrationSample,
  type GazeCalibration,
} from "./gaze";
import { anglesFromMatrix, irisOffset } from "./headPose";
import { VisionLoadError, ensureLandmarkers } from "./mediapipeLoader";
import { faceWidthRatio, FACE, type Landmark } from "./normalize";
import type { FramingState } from "./types";

export type CameraCheckFailureReason =
  | "unsupported"
  | "permission_denied"
  | "no_camera"
  | "camera_busy"
  | "assets_missing"
  | "too_dark"
  | "unknown";

export type CalibrationTarget = "camera" | "screen";

/** Each hold runs this long; the first second is discarded because users take a moment to
 *  settle onto a target. */
const HOLD_MS = 3000;
const SETTLE_MS = 1000;
const SAMPLE_INTERVAL_MS = 80;

/** Healthy head-and-shoulders webcam framing, as a fraction of frame width. */
const FACE_RATIO_MIN = 0.055;
const FACE_RATIO_MAX = 0.13;
/** Nose outside this horizontal band means the user is sitting off to one side. */
const CENTRE_MIN = 0.25;
const CENTRE_MAX = 0.75;
/** Mean luma below this (0-255) is too dark for reliable landmarks. */
const DARK_LUMA = 40;

export interface CameraCheckState {
  /** 0..1 while assets download, else null. */
  loadProgress: number | null;
  isPreparing: boolean;
  isStreaming: boolean;
  failureReason: CameraCheckFailureReason | null;
  /** Live framing verdict, updated continuously once streaming. */
  framing: FramingState;
  brightnessOk: boolean | null;
  /** True once framing has been "good" continuously for the required window. */
  framingSettled: boolean;
  videoRef: React.RefObject<HTMLVideoElement>;
  start: () => Promise<void>;
  stop: () => void;
  /** Capture one 3-second hold. Resolves with how many usable samples it got. */
  captureHold: (target: CalibrationTarget) => Promise<number>;
  /** Fit a calibration from the holds captured so far. */
  fitCalibration: () => GazeCalibration | null;
  captureDimensions: () => { width: number; height: number };
  reset: () => void;
}

/** Framing must hold steady this long before the step passes, so a momentary good frame while
 *  the user is still settling does not count. */
const FRAMING_SETTLE_MS = 2000;

export function useCameraCheck(): CameraCheckState {
  const [loadProgress, setLoadProgress] = React.useState<number | null>(null);
  const [isPreparing, setIsPreparing] = React.useState(false);
  const [isStreaming, setIsStreaming] = React.useState(false);
  const [failureReason, setFailureReason] = React.useState<CameraCheckFailureReason | null>(null);
  const [framing, setFraming] = React.useState<FramingState>("unknown");
  const [brightnessOk, setBrightnessOk] = React.useState<boolean | null>(null);
  const [framingSettled, setFramingSettled] = React.useState(false);

  const videoRef = React.useRef<HTMLVideoElement>(null);
  const streamRef = React.useRef<MediaStream | null>(null);
  const detectRef = React.useRef<((atMs: number) => CalibrationSample | null) | null>(null);
  const rafRef = React.useRef<number | null>(null);
  const timestampRef = React.useRef(0);
  const goodFramingSinceRef = React.useRef<number | null>(null);
  const lumaCanvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const lastLumaCheckRef = React.useRef(0);

  const holdsRef = React.useRef<Record<CalibrationTarget, CalibrationSample[]>>({
    camera: [],
    screen: [],
  });

  const teardown = React.useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    detectRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setIsStreaming(false);
  }, []);

  /** Mean luma over a tiny downscale. ~0.2ms, and it is the difference between telling a user
   *  "you had 8% eye contact" and "your room was too dark to measure". */
  const sampleBrightness = React.useCallback((video: HTMLVideoElement) => {
    let canvas = lumaCanvasRef.current;
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvas.width = 32;
      canvas.height = 24;
      lumaCanvasRef.current = canvas;
    }
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return null;

    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
    let total = 0;
    for (let i = 0; i < data.length; i += 4) {
      total += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    }
    return total / (data.length / 4);
  }, []);

  const evaluateFraming = React.useCallback(
    (landmarks: Landmark[] | undefined, video: HTMLVideoElement): FramingState => {
      if (!landmarks) return "unknown";

      const frame = { width: video.videoWidth, height: video.videoHeight };
      const ratio = faceWidthRatio(landmarks, frame);
      if (ratio === null) return "unknown";

      if (ratio < FACE_RATIO_MIN) return "too_far";
      if (ratio > FACE_RATIO_MAX) return "too_close";

      const nose = landmarks[FACE.noseTip];
      if (nose && (nose.x < CENTRE_MIN || nose.x > CENTRE_MAX)) return "off_center";

      return "good";
    },
    [],
  );

  const start = React.useCallback(async () => {
    if (streamRef.current) return;

    setFailureReason(null);
    setIsPreparing(true);

    try {
      const landmarkers = await ensureLandmarkers({
        models: ["face"],
        onProgress: (fraction) => setLoadProgress(fraction),
      });
      setLoadProgress(null);

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 30 },
          facingMode: "user",
        },
        audio: false,
      });
      streamRef.current = stream;

      const video = videoRef.current;
      if (!video) throw new Error("Camera preview element is not mounted");

      video.srcObject = stream;
      video.muted = true;
      video.playsInline = true;
      await video.play();
      if (!video.videoWidth) {
        await new Promise<void>((resolve) => {
          video.onloadedmetadata = () => resolve();
        });
      }

      // One detect per animation frame, throttled — the check does not need the session's
      // cadence machinery, only a live read of pose and framing.
      detectRef.current = (atMs: number) => {
        // Timestamps must strictly increase for this landmarker instance, same as in the
        // session scheduler; a repeat is a fatal wasm abort rather than a soft error.
        timestampRef.current = Math.max(Math.round(atMs), timestampRef.current + 1);
        const result = landmarkers.face.detectForVideo(video, timestampRef.current);

        const landmarks = result.faceLandmarks?.[0] as Landmark[] | undefined;
        const matrix = result.facialTransformationMatrixes?.[0] as { data: number[] } | undefined;
        const pose = anglesFromMatrix(matrix?.data);

        const nextFraming = evaluateFraming(landmarks, video);
        setFraming(nextFraming);

        if (nextFraming === "good") {
          if (goodFramingSinceRef.current === null) goodFramingSinceRef.current = atMs;
          if (atMs - goodFramingSinceRef.current >= FRAMING_SETTLE_MS) setFramingSettled(true);
        } else {
          goodFramingSinceRef.current = null;
          setFramingSettled(false);
        }

        if (atMs - lastLumaCheckRef.current > 1000) {
          lastLumaCheckRef.current = atMs;
          const luma = sampleBrightness(video);
          if (luma !== null) setBrightnessOk(luma >= DARK_LUMA);
        }

        return pose ? { pose, iris: irisOffset(landmarks) } : null;
      };

      const loop = (now: number) => {
        detectRef.current?.(now);
        rafRef.current = requestAnimationFrame(loop);
      };
      rafRef.current = requestAnimationFrame(loop);

      setIsStreaming(true);
    } catch (err) {
      teardown();
      setLoadProgress(null);
      setFailureReason(toFailureReason(err));
      console.warn("[vision] camera check failed to start:", err);
    } finally {
      setIsPreparing(false);
    }
  }, [evaluateFraming, sampleBrightness, teardown]);

  /**
   * Capture one calibration hold.
   *
   * Samples for HOLD_MS but keeps only what arrives after SETTLE_MS — the first second is the
   * user's eyes travelling to the target, which would drag the median toward wherever they were
   * looking beforehand.
   */
  const captureHold = React.useCallback(async (target: CalibrationTarget): Promise<number> => {
    const samples: CalibrationSample[] = [];
    const startedAt = performance.now();

    await new Promise<void>((resolve) => {
      const tick = () => {
        const elapsed = performance.now() - startedAt;
        if (elapsed >= HOLD_MS) {
          resolve();
          return;
        }
        if (elapsed >= SETTLE_MS) {
          const sample = detectRef.current?.(performance.now());
          if (sample) samples.push(sample);
        }
        window.setTimeout(tick, SAMPLE_INTERVAL_MS);
      };
      tick();
    });

    holdsRef.current[target] = samples;
    return samples.length;
  }, []);

  const fitCalibration = React.useCallback((): GazeCalibration | null => {
    const { camera, screen } = holdsRef.current;
    if (camera.length === 0) return null;
    return calibrateFromTargets(camera, screen);
  }, []);

  const captureDimensions = React.useCallback(() => {
    const video = videoRef.current;
    return { width: video?.videoWidth ?? 0, height: video?.videoHeight ?? 0 };
  }, []);

  const reset = React.useCallback(() => {
    holdsRef.current = { camera: [], screen: [] };
    goodFramingSinceRef.current = null;
    setFraming("unknown");
    setFramingSettled(false);
    setBrightnessOk(null);
    setFailureReason(null);
  }, []);

  React.useEffect(() => {
    // A hard reload skips React's async unmount cleanup, which would leave the camera light on.
    window.addEventListener("pagehide", teardown);
    return () => {
      window.removeEventListener("pagehide", teardown);
      teardown();
    };
  }, [teardown]);

  return {
    loadProgress,
    isPreparing,
    isStreaming,
    failureReason,
    framing,
    brightnessOk,
    framingSettled,
    videoRef,
    start,
    stop: teardown,
    captureHold,
    fitCalibration,
    captureDimensions,
    reset,
  };
}

function toFailureReason(err: unknown): CameraCheckFailureReason {
  if (err instanceof VisionLoadError) {
    if (err.reason === "unsupported_browser") return "unsupported";
    if (err.reason === "assets_missing") return "assets_missing";
    return "unknown";
  }

  switch ((err as { name?: string })?.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "permission_denied";
    case "NotFoundError":
    case "OverconstrainedError":
      return "no_camera";
    case "NotReadableError":
    case "AbortError":
      return "camera_busy";
    default:
      return "unknown";
  }
}
