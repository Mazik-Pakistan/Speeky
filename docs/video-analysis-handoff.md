# Video Delivery Analysis — Handoff & Debugging Guide

Status as of 2026-08-04. Phases 0–5 built; **nothing has ever run against a real camera.** This
document is written for the first real-webcam session: what to run, what will probably break,
and how to tell which failure you're looking at.

Plan: `~/.claude/plans/we-need-to-now-mighty-globe.md` (6 phases).
Phase 6 (Interview Coach reuse) is not started.

---

## 1. What this feature is

Webcam → MediaPipe **in the browser** → aggregated metrics → POST → scored server-side.

**No video, no frames, and no per-frame landmarks ever leave the device.** The backend receives
one JSON object (~11–30 KB). This mirrors the existing audio contract, where the voice socket
streams PCM and the backend only stores derived `AudioFeatures`.

```
webcam (one getUserMedia, one <video>)
  |
  v  requestVideoFrameCallback — ONE model per frame, round-robin
MediaPipe WASM (single-thread SIMD)
  Face 15Hz | Pose 6Hz | Hands 8Hz   (tier: high)
  |
  v  pure sync functions
normalize -> smooth (EMA + hysteresis + dwell) -> metrics/* -> aggregator
  |
  v  POST /public-speaking/{id}/turn  { video_features }
backend/lib/video_scorer.py   (re-applies every coverage gate; trusts nothing)
  |
  v  visual_presence + sub-scores + flags/tips + summary sentence
```

### The video pipeline does NOT use a WebSocket

Worth stating outright, because the code deliberately *reads* like the audio pipeline and the
resemblance misleads. The two are transport-opposites:

| | Audio | Video |
|---|---|---|
| Transport | WebSocket (`/public-speaking/{id}/voice-ws`), streaming | **One HTTP POST at the end** |
| Network during the session | continuous 16kHz PCM up, transcripts down | **none** |
| Where inference runs | backend (SileroVAD + faster-whisper) | browser (MediaPipe WASM) |
| Volume | ~32 KB/s continuous | ~11–30 KB, once |

Audio needs the socket because the transcription models are server-side and it is realtime.
Video has no such need, and streaming frames would break the privacy property the design rests
on for no benefit.

What *is* mirrored is only the contract shape (`audio_features` ↔ `video_features`) and the
hook's API surface — `useVideoAnalysis` matches `useVoiceSocket`'s state names, start/stop, and
consume-once getter on purpose.

**In devtools, for the video path:** no WS connection (its absence is not a bug); a burst of
`/mediapipe/*.wasm` + `.task` fetches on first camera start, then HTTP-cached `immutable`; and
exactly one `POST /public-speaking/{id}/turn`. **Zero image or video content-type requests,
ever** — if you see one, that is a real bug.

### Three invariants — breaking any of these produces confident, wrong coaching

1. **`null` ≠ `0`.** `null` means "not measured". A speaker gesturing below the laptop lid has
   an *unmeasurable* gesture count, not zero gestures. Coverage gates apply to issues and
   highlights too, not just sub-scores.
2. **`overall_score` is byte-identical with and without video.** Video is additive:
   `visual_presence` + `video` block + flags/tips + one summary sentence. Guarded by
   `backend/tests/test_public_speaking_video_integration.py`.
3. **Uncalibrated gaze is not shown.** Below `confidence_weight` 0.35 the results tile hides all
   numbers; below 0.5 nothing reaches an LLM.

---

## 2. Getting it running on the laptop

```bash
git pull

# Frontend — postinstall fetches ~29MB of wasm + models (gitignored, NOT in the repo)
cd frontend
npm ci                      # or: npm install
npm run fetch:mediapipe     # re-run manually if postinstall was skipped/offline
npm run dev

# Backend
cd ../backend
../.venv/Scripts/python.exe -m uvicorn main:app --reload
```

### Prerequisites that bite

- **Assets are gitignored.** `frontend/public/mediapipe/` (~29MB) is reproduced by
  `frontend/scripts/fetch-mediapipe-assets.mjs` on postinstall. It is **non-fatal by design** —
  it logs and exits 0 on network failure, so a successful `npm ci` does *not* prove the assets
  landed. Verify:
  ```bash
  ls -la frontend/public/mediapipe/models/   # 3 .task files
  ls -la frontend/public/mediapipe/wasm/     # vision_wasm_internal.js + .wasm
  cat frontend/public/mediapipe/manifest.json
  ```
- **Prisma client** needs `videoFeatures`. If the laptop's client is stale:
  ```powershell
  # PowerShell, NOT bash — needs .venv\Scripts on a Windows-style PATH
  $env:Path = "<repo>\.venv\Scripts;$env:Path"
  cd backend; & <repo>\.venv\Scripts\python.exe -m prisma generate
  ```
  Bash fails with `spawn prisma-client-py ENOENT`.
- **Migration** `backend/prisma/migrations/20260804000000_add_public_speaking_video_features/`
  adds `videoFeatures JSONB`. Not yet `migrate deploy`-ed to any cloud DB.
- **pytest is not installed in `.venv` by default** despite being in the `dev` group:
  ```bash
  .venv/Scripts/uv.exe pip install --python .venv/Scripts/python.exe pytest pytest-asyncio
  ```

### Test commands

```bash
cd frontend && npm run test:unit     # 122 tests, ~5s, no browser needed
cd backend  && ../.venv/Scripts/python.exe -m pytest -q   # 171 tests
cd frontend && npx tsc --noEmit && npm run build
```

`npm run test:unit` compiles the *pure* vision modules to CommonJS in `test-build/` and runs
`node --test`. No Jest/Vitest — Node 22 strips TypeScript natively. Pass a glob; a bare
directory arg is treated as a module path and fails.

---

## 3. Using it

1. `/dashboard/public-speaking/<speechType>` (e.g. `ted_talk`)
2. Session Setup → keep **Voice** selected → tick **"Also analyse my body language"**
3. **Start Session** → voice readiness gate → **camera check modal** (3 steps)
   - permission/device (this is where ~16MB downloads, with a progress bar)
   - framing (must hold "good" 2s; "Continue Anyway" escape exists)
   - calibration — two 3s holds: look at the lens, then at the middle of the screen
4. Record, speak, stop, submit
5. Results → **Physical Delivery** section

**Skipping calibration is expected to show no numbers.** That is not a bug — see §5.1.

---

## 4. The go/no-go test

This is phase 2's ship criterion and the single most important thing to check.

1. Complete calibration (do not skip).
2. **Stare at the camera lens for ~20s.** Submit.
   → expect `on_camera_pct > 85`
3. New session. **Read from paper on the desk for ~20s.** Submit.
   → expect `down_pct > 70`, `on_camera_pct < 20`

**If those two do not separate cleanly, the gaze pipeline is broken and nothing else matters.**

In simulation the separation is 100/0/0 across lens / on-screen-panel / desk-notes. If reality
disagrees, the geometry assumptions are wrong, not the plumbing — start at §5.3.

To read the raw numbers, either check the network tab (`video_features` on the final `/turn`)
or query:
```sql
select "videoFeatures"->'gaze', "videoFeatures"->'calibration', "videoFeatures"->'quality'
from public_speaking_sessions order by "createdAt" desc limit 1;
```

---

## 5. Debugging guide — likely failures, in rough order of probability

### 5.1 Results tile says "Delivery captured" with no numbers

**Almost certainly correct behaviour, not a bug.** It means `confidence_weight < 0.35`.

Check `videoFeatures->'calibration'->>'method'`:
- `"none"` → calibration was skipped or failed → weight ≈ 0.10 → numbers hidden
- `"session_baseline"` → weak fallback → weight ≈ 0.26 → still hidden
- `"on_screen_target"` + `quality: "good"` → weight ≈ 0.85 → **numbers shown**

Reproduce the exact arithmetic:
```bash
cd backend && ../.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0,'.')
from lib.video_scorer import score_video_session
from services.public_speaking_service import SPEECH_TYPES
import json; f=json.load(open('payload.json'))
s=score_video_session(f, SPEECH_TYPES['ted_talk'])
print(s.confidence_weight, s.rejection, s.detail)
"
```

### 5.2 Nothing happens / camera never starts

Open devtools console. The hook logs `[vision] failed to start video analysis:`.

| Symptom | Cause | Fix |
|---|---|---|
| `VisionLoadError: unsupported_browser` | no wasm SIMD | Chrome/Edge/Safari current |
| `assets_missing`, HTTP 404 on a `.task` | postinstall skipped or offline | `npm run fetch:mediapipe` |
| `NotAllowedError` | permission denied | browser site settings |
| `NotReadableError` | camera held by another app | close Zoom/Teams/OBS |
| Loads forever at some % | 29MB over a slow link | check the network tab |
| **Not on `localhost` or HTTPS** | `getUserMedia` requires a secure context | use `localhost`, not a LAN IP |

That last one is easy to miss: `npm run dev-all` binds `0.0.0.0`, and hitting the app at
`http://192.168.x.x:3000` from another machine **silently has no `navigator.mediaDevices`.**

### 5.3 Gaze does not separate (the go/no-go fails)

Work through in this order:

1. **Is calibration actually good?** `videoFeatures->'calibration'` — `quality` must be `"good"`
   and `method` `"on_screen_target"`. If `weak`, the user moved too much during the holds
   (MAD > 10°) or there were < 8 usable samples.
2. **Is `screen_offset_pitch_deg` sane?** Should be **negative** (panel is below the lens),
   roughly −5° to −20°. If ≈ 0, the two calibration targets did not produce distinguishable head
   positions — the user looked at the same place both times, or the overlay dots are mispositioned
   for their screen.
3. **Is the iris term alive?** `iris_gain_deg_per_unit`. `null` means the iris landmarks were
   unusable (reflective glasses) and gaze fell back to head pose alone, which cannot distinguish
   "head still, eyes down". `25` exactly means the fit was degenerate and it defaulted.
4. **Is the head-pose decode right?** Highly unlikely — `lib/vision/headPose.test.ts` pins the
   column-major convention against hand-computed matrices, including the specific
   nod-is-pitch/shake-is-yaw check. But if pitch and yaw look swapped in the raw data, that is
   where to look.
5. **Cone too tight?** `yaw_tolerance_deg` / `pitch_tolerance_deg`, clamped to 6–15°. A
   `pitch_tolerance_deg` of 6 with a large real screen offset can leave a dead zone.

Relevant code: `lib/vision/gaze.ts` (`calibrateFromTargets`, `classifyGaze`),
`lib/vision/useCameraCheck.ts` (`captureHold` — `HOLD_MS` 3000, `SETTLE_MS` 1000).

### 5.4 Posture / gesture metrics are all null

Check `videoFeatures->'unavailable_reasons'` first — it is designed to answer exactly this.

| Reason | Meaning |
|---|---|
| `pose_not_enabled` | pose model never ran (loader failure) |
| `pose_coverage_0.xx` | model ran, rarely found a body |
| `torso_cropped_0.xx` | shoulders not visible ≥ 60% — **posture is null by design** |
| `posture_baseline_not_established` | < 10 usable frames in the first 10s |
| `hands_out_of_frame` | wrists visible < 25% — gesture null, *not* zero |
| `hand_coverage_0.xx` | hand model ran, rarely found a hand |
| `gaze_uncalibrated` / `gaze_baseline_only` | see §5.1 |
| `iris_unreliable` | eyes disagreed > 30% of frames |
| `blink_rate_undersampled` | face sampling < 12Hz |

The posture baseline is **frozen after the first 10 seconds** (`BASELINE_WINDOW_MS`). If the user
starts slouched, that becomes their "normal" and slouching won't be flagged. This is deliberate
— continuous re-fitting would make any sustained posture invisible — but it means the first 10s
should be a natural sitting position.

### 5.5 Everything is sluggish / video stutters

Check `videoFeatures->'quality'->>'degradation_tier'` and `tier_changes`.

Ladder (`lib/vision/frameScheduler.ts`): `high` 640×480 @ 15/6/8Hz → `medium` 480×360 @
10/4/5 → `low` 320×240 @ 6/3, hands off → `minimal` 320×240 @ 5, face only.

Demotes when mean inference > 45ms or achieved rate < 60% of target, sustained 5s. One
promotion allowed after 30s of headroom, then latched. Below `minimal` at < 4Hz for 10s it calls
`onUnviable` and stops, marking the session `partial`.

If it never demotes despite obvious jank, the cost EMA is not being fed — check
`evaluateLoad` is reached (it runs inside the `isNewFrame` branch).

### 5.6 Hard crash / wasm abort

Almost always **timestamp discipline**. `detectForVideo(video, ts)` requires strictly increasing
timestamps **per landmarker instance**, and the three models see different subsequences of
frames. A shared counter will eventually hand one landmarker a repeat, which aborts the wasm
module rather than throwing something catchable.

Handled in `frameScheduler.ts` via a per-model `lastTimestamp` map, and again in
`useCameraCheck.ts` (`timestampRef`) — the camera-check loop has its *own* counter for the same
face landmarker instance. **If you ever run the check modal and a session simultaneously, those
two counters can collide.** Not currently possible through the UI, but worth knowing.

### 5.7 Left/right coaching is backwards

MediaPipe reports handedness and landmark sides from the **image's** perspective. Image-left is
the user's **right**. Swapped once, at `metrics/hands.ts::userHandFromImage`. The self-view is
CSS-mirrored (`-scale-x-100`) but the frames fed to MediaPipe are **not**.

This trap has already caused two real bugs in this codebase (crossed-arms sign inversion, and a
test that named a variable `left` while passing image-`"Right"`). If left/right reads wrong,
start there.

---

## 6. What is verified vs what is not

### Verified (no camera needed)
- 122 frontend unit tests, 171 backend tests, typecheck, production build
- Column-major matrix decode, pinned against hand-computed matrices
- Gaze geometry separates lens / panel / desk-notes 100/0/0 **in simulation**
- `overall_score` unchanged with and without video, all 5 speech types, both scoring paths
- Coverage gating: absent → null, never zero (both directions)
- MediaPipe result field names checked against `vision.d.ts`:
  `faceLandmarks` / `faceBlendshapes` / `facialTransformationMatrixes`,
  pose `landmarks`, hand `landmarks` + `handedness` (with deprecated `handednesses` fallback)
- Assets restore from nothing; asset-fetch failure is non-fatal

### NOT verified — assume these are wrong until proven otherwise
- **Anything involving a real camera.** The frame loop, `detectForVideo` against live video,
  blendshape extraction, and the whole camera-check modal have never executed.
- **Every threshold is a reasoned default measured against nothing:**
  | Constant | Value | Where |
  |---|---|---|
  | finger-extended ratio | 1.15 | `metrics/hands.ts` |
  | face-touch distance | 1.2 interocular | `metrics/hands.ts` |
  | framing shoulder-width band | 0.18–0.45 of frame | `aggregator.ts` |
  | framing face-width band | 0.055–0.13 | `useCameraCheck.ts` |
  | darkness floor | mean luma 40/255 | `useCameraCheck.ts` |
  | slouch drop | 12% below baseline head-lift | `metrics/posture.ts` |
  | lean depth | ±8% shoulder width | `metrics/posture.ts` |
  | gesture stroke | 0.25 shoulder widths | `aggregator.ts` |
  | fidget window | 1s, path > 8%, range < 12% | `aggregator.ts` |
  | ladder demote | 45ms cost, 5s dwell | `frameScheduler.ts` |
  | calibration hold | 3s, 1s settle | `useCameraCheck.ts` |
- `track.applyConstraints()` mid-session (tier demotion) has never run.
- A build failed **once** with `Failed to collect page data for /dashboard/accent-assessment` —
  a page untouched by this work. Did not reproduce; a clean `rm -rf .next && npm run build`
  passes. Flagging rather than burying it.

---

## 7. Where things live

### Frontend
```
lib/vision/
  types.ts             VideoFeatures contract (mirror of the Pydantic schema)
  mediapipeLoader.ts   lazy singleton; FilesetResolver + landmarkers
  frameScheduler.ts    rVFC loop, per-model cadence, degradation ladder
  normalize.ts         THE only place landmark arithmetic is allowed
  smoothing.ts         EMA, Schmitt trigger, dwell+refractory, excursions
  headPose.ts          column-major matrix decode + iris offset
  gaze.ts              calibration fitting + gaze classification
  aggregator.ts        accumulates everything into the payload
  useVideoAnalysis.ts  the session hook (mirrors useVoiceSocket)
  useCameraCheck.ts    the 3-step check + calibration capture
  metrics/posture.ts   posture, lean, sway, pose-tier gesture
  metrics/hands.ts     finger-level shapes, proximity, clasping
lib/cameraReadiness.ts                        30-min TTL + calibration persistence
components/common/CameraReadinessGate.tsx
components/dashboard/progress/CameraCheckModal.tsx
components/dashboard/public-speaking/DeliverySparkline.tsx
app/dashboard/public-speaking/[speechType]/page.tsx    toggle, self-view, results
```

### Backend
```
schemas/video_features_schema.py   the contract (extra="ignore" for forward compat)
lib/video_scorer.py                scoring; imports NOTHING from services/ (reuse boundary)
lib/prompts.py                     build_video_presence_note (for phase 6's LLM grader)
services/public_speaking_service.py  wiring; _generate_scorecard, _append_presence_sentence
prisma/schema.prisma               PublicSpeakingSession.videoFeatures Json?
```

**Public Speaking has no LLM grader** — `_generate_feedback_summary` is a deterministic
template, and that template *is* the narrative. `build_video_presence_note` exists for the
Interview Coach (phase 6), which does have one.

### localStorage keys
```
speeky.cameraReadiness.lastPassedAt   30-min TTL
speeky.cameraCalibration.v1           {calibration, videoWidth, videoHeight, savedAt}
```
Clearing these forces the check modal to reappear. Calibration is invalidated automatically on
resolution change or after 24h.

---

## 8. Quick sanity checklist for the first camera session

- [ ] `npm run test:unit` → 122 pass
- [ ] `pytest -q` → 171 pass
- [ ] All 3 `.task` files + wasm present in `public/mediapipe/`
- [ ] App served over `localhost` or HTTPS (not a LAN IP)
- [ ] Camera **off** → submit → `overall_score` matches a pre-change baseline, no `videoFeatures`
- [ ] Camera **on** → modal appears → framing gate blocks when off to one side
- [ ] Calibration completes with `quality: "good"`
- [ ] **Go/no-go**: lens ≈ >85% on-camera; desk notes ≈ >70% down
- [ ] Network tab: **zero** image/video content-type requests; payload < 50KB
- [ ] End session → OS camera light off within 1s; navigate away mid-session → same
- [ ] DevTools CPU throttle 6× → tier demotes; gesture metrics come back `null` not `0`
- [ ] DB: `videoFeatures` holds aggregates + timeline, **no frame or landmark arrays**
