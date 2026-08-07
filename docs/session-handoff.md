# Session Handoff — 2026-08-08

Continuation notes for picking this up on another machine. Companion to
`docs/video-analysis-handoff.md`, which covers the video pipeline in depth; this file covers
**what changed in the last session, what state the repo is in, and where to start debugging.**

---

## 0. Read this first — the backend tests do not travel

`backend/.gitignore:17` is `tests/**`. There are **15 test files and 320 passing tests on the
dev machine, and zero of them are in git.**

```bash
ls backend/tests/*.py | wc -l   # 15
git ls-files backend/tests/     # (empty)
```

A fresh clone gets no backend tests at all, despite `backend/pyproject.toml` declaring
`testpaths = ["tests"]`. `pytest -q` on the laptop will collect nothing and pass vacuously,
which looks like success.

This was a deliberate call ("leave as is") when it was only a hygiene issue. For a machine
handoff it is a blocker. Pick one:

- **Copy `backend/tests/` across manually** (USB, zip, scp) — keeps the ignore rule intact.
- **Or drop the ignore**: delete line 17 of `backend/.gitignore`, `git add backend/tests`,
  commit. This is what I would do — the suite is the only thing enforcing the invariants below,
  and unversioned it protects nobody.

Frontend tests are unaffected: `frontend/lib/vision/*.test.ts` (8 files, 126 tests) are tracked
and travel normally.

---

## 1. Repo state

```
branch   Testing-Video
HEAD     61a7716  Avatar Integration into PSC
         eb1fd54  Merge remote-tracking branch 'origin/main' into Testing-Video
         fdb0d03  add livekit agent with avatar and some fixes (#474)   <- coworker's
```

Working tree clean. `Testing-Video` now contains **both** the video pipeline and the coworker's
LiveKit/avatar work. `main` does **not** have the video pipeline — do not develop there.

Untracked-but-needed on any machine (both gitignored, both regenerable):
- `frontend/public/mediapipe/` — ~29MB, restored by `npm ci` (postinstall) or
  `npm run fetch:mediapipe`
- `frontend/test-build/` — compiled output of `npm run test:unit`, disposable

### Bring-up

```bash
git switch Testing-Video && git pull

cd frontend && npm ci          # postinstall fetches the ~29MB of wasm + models
npm run test:unit              # 126 expected
npm run dev                    # must be localhost or HTTPS — see §4

cd ../backend
../.venv/Scripts/python.exe -m pytest -q    # 320 IF you copied tests/ across, else 0
# prisma client must know videoFeatures — PowerShell, not bash:
#   $env:Path = "<repo>\.venv\Scripts;$env:Path"; python -m prisma generate
uv run uvicorn main:app --reload

# separate process, only needed for the avatar Q&A:
cd backend && uv run python -m live_call.worker dev
```

---

## 2. What changed last session

### Phase 0 — merge + env
Merged `origin/main` into `Testing-Video`. Only two conflicts, both dependency files.

**Fixed the avatar env mismatch.** `live_call/worker.py:92` reads `BEY_API_KEY` /
`BEY_AVATAR_ID`; `.env` had `BEYOND_PRESENCE_API_KEY` / `AVATAR_ID`. Neither matched, so
`_start_avatar_or_skip` returned False and every call silently ran audio-only. **`.env` is
gitignored — this rename has to be redone by hand on the laptop.**

Deleted `backend/voice_agent/.env` (its three LiveKit values were byte-identical to the ones in
`backend/.env`, verified by hash) and an orphaned `livekit_tokens.cpython-313.pyc`.

### Phase 1 — calibration
Root cause was sampling, not thresholds: `captureHold` ran a second `detectForVideo` on an 80ms
timer while the rAF loop was already detecting every frame. Collection moved into that loop
(~5x samples, half the CPU). Added a 3-2-1 countdown with the target dot visible, `MIN_SAMPLES`
8→5, `MAX_USABLE_MAD_DEG` 10→14, and a silent auto-retry.

Two correctness fixes fell out:
- The tolerance cone is capped strictly inside the measured screen offset. A widened cone was
  swallowing it, so panel gaze scored as lens contact — inflating `on_camera_pct` for exactly
  the restless users whose data deserves least confidence.
- `screenOffsetPitchDeg` is now computed in **gaze space** (head + iris), matching what
  `classifyGaze` compares it against. It was head-only, understating the real gap by ~half.

### Phase 2 — emotional register
`backend/lib/register_scorer.py`. Scores delivery against what the scenario asks for, per speech
type, across three channels — voice arousal, facial warmth, lexical formality. Each is `None`
when its source is absent, never 0. **Never emits an emotion label**;
`test_no_issue_ever_names_an_emotion` sweeps every combination and enforces it.

`voice_ws.py`'s `"full"` tier now also carries `mean_pitch_hz` and `intensity_variation_db`
(both were already computed and discarded), and `snr_db` finally reaches the server — it was
sent but dropped by the client type, so `voice_clarity` scored a constant ~85.3 for every
live-voice session.

**Scoring boundary:** the voice channel modulates `tone_variation` / `audience_engagement` and
therefore `overall_score` for spoken sessions (`scoring_version: 2`). Face and words do not —
same comparability reasoning that keeps `visual_presence` out.

### Phase 3 — avatar Q&A
`public_speaking` is now a Live Call feature, **Q&A only**. Three independent guards keep the
agent out of the speech phase: the backend token gate (`status == "qa_phase"`), the dispatch
setup builder, and the UI only offering the call on the results screen. A live participant
during a monologue would talk over the speaker *and* have its voice transcribed into the audio
being scored (`useVoiceSocket` captures with **no echo cancellation**).

`@livekit/components-react` is loaded via `next/dynamic` with `ssr: false`. Static import put
~150kB in the page bundle for every visitor (First Load 137kB → 288kB). **Keep it lazy.**

---

## 3. Invariants — if one of these breaks, that is the bug

1. **`null` != `0`.** A metric that could not be measured is null. "Hands out of frame" must
   never render as "zero gestures".
2. **Camera on and camera off produce the same `overall_score`.** Video is additive.
3. **Text-mode sessions are untouched by register.** Only the voice channel moves the headline.
4. **Uncalibrated gaze is never shown as a number** — below `confidence_weight` 0.35 the tile
   withholds; below 0.5 nothing reaches an LLM.
5. **No output copy ever names an emotion.**

---

## 4. Debugging — likely failure classes

I do not know which errors the laptop is throwing. Paste the exact message and I can be
specific; meanwhile these are the ones this stack actually produces, roughly by likelihood.

### Frontend won't build / typecheck
- `Failed to patch lockfile … Cannot read properties of undefined (reading 'os')` — **benign**.
  A Next warning after `package-lock.json` was regenerated. The build still exits 0; check for
  `✓ Compiled successfully` and a route table rather than trusting the warning.
- Missing `@mediapipe/tasks-vision` or `livekit-client` → `npm ci` wasn't run after the merge.

### Camera does nothing
- **Not on `localhost` or HTTPS.** `npm run dev-all` binds `0.0.0.0`; visiting
  `http://192.168.x.x:3000` leaves `navigator.mediaDevices` **undefined** with no error. This
  is the single most common false alarm.
- 404 on a `.task` or `.wasm` → assets missing. `npm run fetch:mediapipe`. Note the fetch script
  is non-fatal by design, so `npm ci` succeeding does **not** prove the assets landed.
- Console logs `[vision] failed to start video analysis:` with a reason — see
  `video-analysis-handoff.md` §5.2.

### Results show "Delivery captured" with no numbers
Working as designed — calibration was skipped or failed, `confidence_weight ≈ 0.10`. Check
`videoFeatures->'calibration'->>'method'`. `on_screen_target` + `good` is the only combination
that displays numbers.

### Backend import errors
- `ModuleNotFoundError: lib.register_scorer` → stale checkout, or you are on `main`.
- Prisma errors mentioning `videoFeatures` → `prisma generate` not run. Must be PowerShell with
  `.venv\Scripts` on a Windows PATH; bash fails with `spawn prisma-client-py ENOENT`.
- `pytest` collecting 0 tests → §0, the tests are not in git.

### Avatar never appears
- `BEY_API_KEY` unset or misnamed → **silent** audio-only fallback, nothing in the logs. `.env`
  is gitignored, so the Phase 0 rename must be redone on this machine.
- Token request 404s → the session is not in `qa_phase`; the gate is working.
- Worker not running → it is a separate process, not part of FastAPI.

---

## 5. What has never been verified

Nothing from last session ran against a real camera or a real LiveKit room. Assume all of it is
unproven:

- calibration countdown feel, and whether it now succeeds first-try in practice
- the register bands against real speech (a flat toast *should* now score below an animated one)
- the entire avatar path — worker dispatch, room join, avatar video, one-exchange completion
- `track.applyConstraints()` mid-session (tier demotion)

Every threshold in the vision layer is a reasoned default measured against nothing — the full
table is in `video-analysis-handoff.md` §6.

---

## 6. Next planned work

Approved plan lives at `~/.claude/plans/we-need-to-now-mighty-globe.md` (not in the repo).
Phases 0–3 are done. Outstanding:

- **Real-camera pass** on all three phases (§5)
- **Interview Coach reuse** of the video pipeline — the payoff test for the reusability
  boundary. If `frontend/lib/vision/*` or `backend/lib/video_scorer.py` need *any* change, the
  boundary was drawn wrong. Needs `ALTER TYPE "CoachingInputMode" ADD VALUE 'AUDIO_VIDEO'` in
  **its own migration file** — PostgreSQL cannot add an enum value alongside other statements
  in one transactional migration.
- **Multi-question Q&A** — currently one exchange, because `submit_qa_response` completes the
  session. Would need a backend change.
