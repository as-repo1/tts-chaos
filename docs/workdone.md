# TTS Chaos — Work Done Log

This file is the maintenance record for the repository. It is intentionally written as a running history rather than a one-shot status sheet.

---

## Status legend

| Symbol | Meaning |
|---|---|
| ✅ | Completed and verified |
| 🔧 | Present and functional but still limited |
| 📄 | Documentation only |
| ⏳ | Planned or in-progress |
| ❌ | Not yet implemented |

---

## Session 2026-08-05 — Production hardening pass

### ✅ Startup and runtime import path repaired

The repo was re-verified with a live FastAPI test client. The import path now boots cleanly and serves endpoints under the app’s actual runtime config.

Verified evidence:

- `GET /api/health` returned `200` with `{"status": "ok"}`
- `GET /api/system/info` returned `200` and exposed the expected system fields

### ✅ Broken persistence dependency restored

A real startup regression was identified and fixed at the root cause level:

- `voices_store` and `VoiceRecord` were missing from the DB layer integration surface used by the document batch flow
- the app was failing to import before it could respond to health or system requests

That compatibility gap was restored so the code can now start and serve runtime endpoints again.

### ✅ Container and deployment assumptions tightened

The container build path was rewritten to align with the repo’s real package metadata rather than a non-existent `requirements.txt` artifact.

Changes in scope:

- Docker image builds from `pyproject.toml` and the editable package install path
- runtime host/port settings are environment-driven
- docs exposure is disabled by default in the container baseline
- CORS is no longer wildcarded in the default shipped config

### ✅ Runtime documentation aligned with the real codebase

The markdown docs were refreshed so future maintainers read the system’s operational reality instead of a stale stub-era narrative.

---

## Session 2026-08-03 — Architecture and engine foundation

### ✅ Project shape and foundational system pieces were added

This work established the app’s central runtime and service separation:

- FastAPI application entrypoint and startup hook
- API routers for voice and model activity
- SQLite-backed voice persistence
- Model catalog and engine manager abstraction
- Frontend shell and static bundle

### ✅ Real engine abstraction was introduced

The codebase now centers on a pluggable engine architecture:

- `edge-tts` for cloud fallback
- `kokoro` for local ONNX inference
- `piper` for local Piper model inference
- `xtts` for cloning-oriented voice synthesis work

### ✅ Documenting the architecture continued

The repo now contains a maintenance-friendly markdown set covering architecture, process flow, and current implementation context.

---

## Current operational posture

| Area | Status |
|---|---|
| Local startup path | ✅ Functional |
| Container deployment path | ✅ Repaired for the project metadata shape |
| Health endpoint | ✅ Present |
| System info endpoint | ✅ Present |
| DB-backed voice records | ✅ Present |
| Local model download workflow | ✅ Present |
| Batch document generation | 🔧 In place as a background MVP |
| XTTS-specific clone workflow | 🔧 Present but engine-dependent |
| Hard production hardening | 🔧 In progress, but the baseline is now sensible |

---

## Recommended next work

### ⏳ Operational hardening

- Add a non-root container user
- Add explicit readiness/liveness probes
- Add structured logs and request correlation
- Add retry/backoff and cancellation semantics around large downloads

### ⏳ Reliability work

- Make queue-backed document job state durable across process restarts
- Add model download checksum or integrity verification
- Add a safer concurrency and rate-limit layer for generation jobs

### ⏳ UX polish

- Push the “Settings” tab and runtime preferences into the frontend surface
- Make model state, engine state, and asset usage more human-readable in the UI

---

## Summary

The repo is now in a much more maintainable place than the original stub state:

- the runtime can be imported and exercised
- key endpoints are live
- deployment assumptions are no longer contradicted by the Docker files
- the docs now explain the codebase at the level a future maintainer needs

That is the correct baseline to build from for the next production-focused cycle.

