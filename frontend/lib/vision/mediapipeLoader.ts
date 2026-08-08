"use client";

/**
 * Lazily instantiates the MediaPipe landmarkers, once per page load.
 *
 * The wasm runtime is ~12MB and each model is another 4-8MB, so this must never run during SSR
 * or on a page the user hasn't opted into the camera on. Two things keep that true:
 *
 *   - the `@mediapipe/tasks-vision` import is dynamic, so webpack emits it as its own async
 *     chunk that is only fetched when `ensureLandmarkers()` is first called; and
 *   - `ensureLandmarkers()` is only reachable from `startVideo()`, which is a user gesture.
 *
 * The `typeof window` guard below is belt-and-braces for the case where someone later calls
 * this from a server component by mistake — a clear throw beats a confusing wasm abort.
 *
 * Landmarkers are cached at module scope deliberately. Re-instantiating costs 1-2s of wasm
 * setup even with the models warm in the HTTP cache, which would be paid on every session.
 * `closeLandmarkers()` exists for teardown but is not called between sessions.
 */

import type {
  FaceLandmarker,
  HandLandmarker,
  PoseLandmarker,
} from "@mediapipe/tasks-vision";

/** Served from public/mediapipe/, populated by scripts/fetch-mediapipe-assets.mjs. */
const WASM_BASE = "/mediapipe/wasm";
const MODEL_BASE = "/mediapipe/models";
const MANIFEST_URL = "/mediapipe/manifest.json";

export type ModelKind = "face" | "pose" | "hand";

export type VisionLoadFailure =
  | "unsupported_browser"
  | "assets_missing"
  | "load_failed";

export class VisionLoadError extends Error {
  readonly reason: VisionLoadFailure;

  constructor(reason: VisionLoadFailure, message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "VisionLoadError";
    this.reason = reason;
  }
}

export interface Landmarkers {
  face: FaceLandmarker;
  pose: PoseLandmarker | null;
  hand: HandLandmarker | null;
  /** Pinned model revisions, surfaced through video_features.quality.model_versions. */
  versions: Partial<Record<ModelKind, string>>;
}

export interface EnsureOptions {
  /** Phase 1 loads face only. Pose and hands arrive in phases 3 and 4. */
  models?: ModelKind[];
  /** 0..1, for the "Preparing analysis..." progress in the camera check modal. */
  onProgress?: (fraction: number, label: string) => void;
  signal?: AbortSignal;
}

let landmarkersPromise: Promise<Landmarkers> | null = null;
let cached: Landmarkers | null = null;

function assertClient() {
  if (typeof window === "undefined") {
    throw new VisionLoadError(
      "load_failed",
      "MediaPipe can only be initialised in the browser — ensureLandmarkers() was called during SSR.",
    );
  }
}

async function fetchModelVersions(signal?: AbortSignal): Promise<Partial<Record<ModelKind, string>>> {
  // Non-fatal: a missing manifest costs provenance on stored aggregates, not the feature.
  try {
    const response = await fetch(MANIFEST_URL, { signal, cache: "force-cache" });
    if (!response.ok) return {};
    const manifest = (await response.json()) as Partial<
      Record<ModelKind, { version?: string }>
    >;
    return Object.fromEntries(
      (Object.keys(manifest) as ModelKind[])
        .map((key) => [key, manifest[key]?.version])
        .filter((entry): entry is [ModelKind, string] => typeof entry[1] === "string"),
    );
  } catch {
    return {};
  }
}

/**
 * Fetch a `.task` bundle as bytes so it can go to `createFromModelBuffer`.
 *
 * `createFromModelPath` would fetch it again internally, and gives no progress events — which
 * matters when the user is staring at a modal waiting on ~16MB.
 */
async function fetchModel(
  file: string,
  signal: AbortSignal | undefined,
  onBytes: (loaded: number, total: number) => void,
): Promise<Uint8Array> {
  const response = await fetch(`${MODEL_BASE}/${file}`, { signal, cache: "force-cache" });
  if (!response.ok) {
    throw new VisionLoadError(
      "assets_missing",
      `${file} is missing (HTTP ${response.status}). Run \`npm run fetch:mediapipe\` — it normally runs on postinstall.`,
    );
  }

  const total = Number(response.headers.get("content-length") ?? 0);
  if (!response.body) {
    const buffer = new Uint8Array(await response.arrayBuffer());
    onBytes(buffer.byteLength, buffer.byteLength);
    return buffer;
  }

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let loaded = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    loaded += value.byteLength;
    onBytes(loaded, total || loaded);
  }

  const out = new Uint8Array(loaded);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return out;
}

async function load(options: EnsureOptions): Promise<Landmarkers> {
  assertClient();

  const models = options.models ?? ["face"];
  const { onProgress, signal } = options;
  const report = (fraction: number, label: string) => onProgress?.(fraction, label);

  report(0.02, "Loading vision runtime");

  // Dynamic so webpack splits it into its own chunk — see the module docstring.
  const vision = await import("@mediapipe/tasks-vision");
  const { FilesetResolver, FaceLandmarker, PoseLandmarker, HandLandmarker } = vision;

  // Only the SIMD wasm is shipped (see scripts/fetch-mediapipe-assets.mjs). Without SIMD,
  // FilesetResolver would request the _nosimd_ pair and 404, so fail with a reason the UI can
  // explain rather than an opaque fetch error.
  if (!(await FilesetResolver.isSimdSupported())) {
    throw new VisionLoadError(
      "unsupported_browser",
      "This browser lacks WebAssembly SIMD, which the vision pipeline requires.",
    );
  }

  const fileset = await FilesetResolver.forVisionTasks(WASM_BASE);
  report(0.15, "Loading models");

  const versions = await fetchModelVersions(signal);

  // Weight progress by real download size so the bar doesn't stall on the biggest file.
  const specs: Record<ModelKind, { file: string; bytes: number }> = {
    face: { file: "face_landmarker.task", bytes: 3_758_596 },
    pose: { file: "pose_landmarker_lite.task", bytes: 5_777_746 },
    hand: { file: "hand_landmarker.task", bytes: 7_819_105 },
  };
  const totalBytes = models.reduce((sum, kind) => sum + specs[kind].bytes, 0);
  let completedBytes = 0;

  const buffers = {} as Record<ModelKind, Uint8Array>;
  for (const kind of models) {
    buffers[kind] = await fetchModel(specs[kind].file, signal, (loaded) => {
      const fraction = (completedBytes + loaded) / totalBytes;
      report(0.15 + fraction * 0.7, "Loading models");
    });
    completedBytes += specs[kind].bytes;
  }

  report(0.9, "Starting analysis");

  const face = await FaceLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetBuffer: buffers.face, delegate: "GPU" },
    runningMode: "VIDEO",
    numFaces: 1,
    // The two flags that make separate emotion and gaze models unnecessary: blendshapes are
    // the FACS-style signals, and the transform matrix is head pose.
    outputFaceBlendshapes: true,
    outputFacialTransformationMatrixes: true,
  });

  const pose = models.includes("pose")
    ? await PoseLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetBuffer: buffers.pose, delegate: "GPU" },
        runningMode: "VIDEO",
        numPoses: 1,
      })
    : null;

  const hand = models.includes("hand")
    ? await HandLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetBuffer: buffers.hand, delegate: "GPU" },
        runningMode: "VIDEO",
        numHands: 2,
      })
    : null;

  report(1, "Ready");
  return { face, pose, hand, versions };
}

/**
 * Resolve the landmarkers, loading them on first call.
 *
 * Concurrent callers share one in-flight promise — two components mounting at once must not
 * trigger two 16MB downloads. A failed load clears the cache so a retry can actually retry.
 */
export function ensureLandmarkers(options: EnsureOptions = {}): Promise<Landmarkers> {
  if (cached) {
    options.onProgress?.(1, "Ready");
    return Promise.resolve(cached);
  }
  if (!landmarkersPromise) {
    landmarkersPromise = load(options)
      .then((landmarkers) => {
        cached = landmarkers;
        return landmarkers;
      })
      .catch((error) => {
        landmarkersPromise = null;
        throw error instanceof VisionLoadError
          ? error
          : new VisionLoadError("load_failed", "Could not start the vision pipeline.", {
              cause: error,
            });
      });
  }
  return landmarkersPromise;
}

/** True once the assets are warm, so the UI can skip the "Preparing analysis" step. */
export function landmarkersReady(): boolean {
  return cached !== null;
}

/** Full teardown. Not called between sessions — see the module docstring. */
export function closeLandmarkers(): void {
  cached?.face.close();
  cached?.pose?.close();
  cached?.hand?.close();
  cached = null;
  landmarkersPromise = null;
}
