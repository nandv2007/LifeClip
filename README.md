# LifeClip

> **Every photo should be actionable.**

LifeClip turns passive photos into **actions**. Snap a poster, receipt, ticket, handwritten note,
menu, product label or notice — LifeClip understands what it is, extracts the information that
matters, and suggests the 2–5 most useful things to do next. You review, edit, and confirm.

```
CAPTURE → UPLOAD → UNDERSTAND → CLASSIFY → EXTRACT → RECOMMEND → REVIEW/EDIT → ACT
```

**Privacy by design — non-negotiable:**

> **"LifeClip only sees what you choose to capture or upload. We never scan your gallery."**

- Never requests full-gallery access. Never scans. Never monitors.
- The user explicitly captures **one** photo or picks **one** file. That's the entire input.
- Delete controls (per-item and full wipe) are built in, and the Cloudinary copy is deleted too.

---

## Features

| Capability | What it does |
|---|---|
| **Capture** | In-browser camera (with straight-to-file fallback), single explicit file picker, drag & drop, JPEG/PNG/WebP, ≤ 10 MB, validated client- and server-side |
| **Real Cloudinary pipeline** | Signed direct uploads (secret never leaves the server), asset verification via Admin API, organized under `lifeclip/`, optimized delivery (`f_auto`, `q_auto`), responsive thumbnails/previews, secure deletion |
| **Understanding** | Local OCR (Tesseract) → category classification → structured extraction per category → confidence + warnings |
| **Action engine** | Category-specific ranked actions (calendar, reminder, directions, expense, warranty, summarize, quiz, flashcards, translate, search, share, copy) |
| **Editable extraction** | Every important field can be corrected; user edits are marked and trusted |
| **Confirmation before acting** | Calendar/reminder screens show editable name/date/time/location/reminder, then download a real `.ics` (works with Google/Apple/Outlook) |
| **Study tools** | Summarize, explain, quiz-me (fill-in-the-blank), flashcards — generated **only** from the extracted text |
| **History** | Only items you submitted: thumbnails, search, category filters, delete |
| **Settings** | Privacy, retention (30d/90d/1y/forever), store-text toggle, delete-all-data, reduce-motion + larger-text |
| **Honest states** | queued → uploading → analyzing (Understanding / Finding useful information / Preparing actions) → ready / partial / failed, with retry. No fake progress. |

### What it knows how to read

| Category | Extracts | Example actions |
|---|---|---|
| Event poster | name, date, time, venue, link, contact | Add to Calendar · Set Reminder · Find Location |
| Receipt | merchant, date, total, currency, item lines, return/warranty clues | Save Purchase · Save as Expense · Return/Warranty Reminder |
| Ticket | event/journey, date, time, seat, PNR/reference, route | Add to Calendar · Reminder · Save Ticket |
| Study notes | full text, topic, key concepts, length | Summarize · Quiz Me · Flashcards · Explain |
| Menu | dishes with prices, dish count | Translate · Save Menu |
| Product | product, model, brand, warranty, specs on label | Save Product · Find Manual/Search · Warranty Reminder |
| Notice/document | title, dates, deadline, email/phone, link | Summarize · Reminder · Save |
| Unknown | whatever text exists (graceful, never empty) | Copy Text · Summarize · Translate · Save · View Original |

---

## Architecture

```
┌────────────────────────────┐         signed params          ┌───────────────────────────┐
│  React + TypeScript (Vite) │ ◄───────────────────────────── │  FastAPI backend          │
│  (mobile-first PWA-style)  │                                │  ── upload-signature ──── │
└──────┬─────────────────────┘                                │  ── clips CRUD / analyze  │
       │ 1) POST /api/upload-signature                        │  ── actions / confirm     │
       │ 2) direct upload (XHR, real progress)                │  ── settings / account    │
       ▼                                                      │  ── analysis worker       │
┌────────────────────────────┐  3) asset JSON                │  ── ICS generation        │
│  CLOUDINARY (tecwmb40)     │ ──────────► (browser)         │  ── study tools (local)   │
│  folder: lifeclip/         │                                └────┬──────────────┬───────┘
│  ── secure storage         │  4) POST /api/clips {public_id}     │ Admin API    │ delivery
│  ── delivery + transforms  │ ───────────────────────────────►verify+fetch  download
│  ── f_auto/q_auto/thumbs   │                                ┌───▼──────────────▼───────┐
└────────────────────────────┘                                │  Analysis pipeline:      │
       ▲  5) analyzer downloads optimized PNG                 │  OCR → classify → extract│
       └──────────────────────────────────────────────────────│  → actions → warnings    │
                                                              └─────────────┬────────────┘
┌────────────────────────────┐                                             │
│  Relational DB             │ ◄────────────────────────────────────────────┘
│  PostgreSQL (prod) /       │   sessions · clips · extracted_fields ·
│  SQLite (zero-config dev)  │   actions · analysis_runs · session_settings
└────────────────────────────┘
```

### Why this upload flow (signed direct upload)

1. Browser asks `POST /api/upload-signature` (file type + size validated first).
2. Backend builds params (`folder=lifeclip`, `public_id=lifeclip/<uuid>`, `timestamp`, `tags`, `context`)
   and signs them with the API secret: `SHA1(sorted_params + api_secret)` — **the secret never
   leaves the server**.
3. Browser uploads the file **directly to Cloudinary** with those params (fast, resumable-grade path,
   with genuine XHR progress).
4. Browser tells the backend the resulting `public_id`.
5. Backend **re-verifies** the asset with the authenticated **Admin API** (never trusting client
   claims), stores canonical metadata, then analyzes.
6. Delivery uses unsigned, optimized transformation URLs — thumbnails and previews are cheap.

---

## Getting started (local development)

### Prerequisites

- Python 3.11+, Node 20+
- **Tesseract OCR**: `sudo apt-get install tesseract-ocr` (Debian/Ubuntu) or `brew install tesseract` (macOS)

### One-command setup

```bash
./scripts/dev.sh
```

It installs dependencies, starts the API on `:8787` and the frontend on `:5173`.

### Manual setup

```bash
# 1) Cloudinary credentials (from console.cloudinary.com → "Go to API Keys")
cp backend/.env.example backend/.env
#   → edit backend/.env: CLOUDINARY_API_KEY=..., CLOUDINARY_API_SECRET=...
#   (cloud name is preset to tecwmb40; folder preset to lifeclip)

# 2) Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8787

# 3) Frontend (new terminal)
cd frontend
npm install
npm run dev        # http://localhost:5173, proxies /api → :8787
```

> **Without credentials the app still runs**, but uploads pause with a clear in-app banner and an
> honest 503 from the API — there is no fake Cloudinary fallback.

### Exact macOS instructions (permanent local install)

```bash
# 0) Prerequisites (one time, via Homebrew — https://brew.sh)
brew install python@3.12 node tesseract
#   python includes pip; node includes npm; tesseract powers the real OCR.
#   (optional, for PostgreSQL instead of SQLite: brew install docker, or install Docker Desktop)

# 1) Unzip and enter the project
unzip LifeClip_Final_Verified.zip && cd LifeClip

# 2) Put YOUR Cloudinary credentials in backend/.env  ← this exact file
cd backend
cp .env.example .env                 # template with variable names, no secret values
#   edit backend/.env and fill these two lines with your own values from
#   console.cloudinary.com → your cloud → "Go to API Keys":
#     CLOUDINARY_API_KEY=your_key_here
#     CLOUDINARY_API_SECRET=your_secret_here
#   CLOUDINARY_CLOUD_NAME and CLOUDINARY_FOLDER are already preset.
#   backend/.env is gitignored — the secret stays on your machine only.

# 3) Create a virtual environment and install backend deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4) Start the API (SQLite is the default dev database — no DB install needed)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8787
#   → should log: cloudinary=configured
#   Optional PostgreSQL: docker compose up -d (from the project root), then set
#   DATABASE_URL=postgresql+psycopg://lifeclip:lifeclip@localhost:5432/lifeclip in backend/.env

# 5) Frontend (in a SECOND Terminal window)
cd LifeClip/frontend
npm install
npm run dev

# 6) Open the app
#   Frontend : http://localhost:5173    ← use this
#   API      : http://localhost:8787    (docs at /docs, health at /api/health)

# 7) Prove Cloudinary works on your account (one command, from backend/)
python scripts/verify_cloudinary.py
#   Expected: signed upload → real upload → admin verify → cleanup, exit code 0.

# 8) Run the full test suite
python -m pytest tests/ -q            # 43 tests
```

Works identically on Apple Silicon and Intel; if `tesseract` is missing the analyzer
reports an honest OCR-failure state instead of faking results.

### Verify Cloudinary end-to-end (one command)

```bash
cd backend && python scripts/verify_cloudinary.py
```

Signs parameters, uploads a real sample image to `tecwmb40/lifeclip/`, verifies it via the Admin
API, prints working delivery/thumbnail URLs, and cleans up after itself.

### Database

- **Default (dev):** SQLite at `backend/var/lifeclip.db` — zero setup.
- **Production-grade:** PostgreSQL 17 (the whole test suite passes against it):

```bash
docker compose up -d        # starts PostgreSQL
# backend/.env:
DATABASE_URL=postgresql+psycopg://lifeclip:lifeclip@localhost:5432/lifeclip
```

---

## API reference

Base: `/api`. Every request (except `/api/health`) carries the anonymous session header
`X-Lifeclip-Session: <token>` (generated on-device, no account). Errors are always
`{"error": {"code": "...", "message": "human readable"}}` with appropriate status codes.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness: db status, `cloudinary_configured` (never credentials) |
| POST | `/api/upload-signature` | Validate file → one-time signed Cloudinary params. 415 unsupported type, 413 too large, 503 not configured |
| POST | `/api/clips` | Register an uploaded asset (Admin-API verified). 201 + clip |
| GET | `/api/clips?q=&category=` | History list for this session (search + filter) |
| GET | `/api/clips/:id` | Clip detail: status, fields (with confidence), actions, text |
| PATCH | `/api/clips/:id` | Edit title/category |
| PATCH | `/api/clips/:id/fields` | Edit/add/remove extracted fields (user edits marked, confidence → 1.0) |
| DELETE | `/api/clips/:id` | Delete DB rows **and** the Cloudinary asset (honest report) |
| POST | `/api/clips/:id/analyze` | Start analysis. **Idempotent** — an active run is reused, so refresh never duplicates. `{force:true}` retries after failure |
| GET | `/api/clips/:id/analysis` | Poll truthful status + phase (queued/understanding/extracting/actions) |
| POST | `/api/clips/:id/study` | `{mode: summary\|explain\|quiz\|flashcards}` → grounded in extracted text |
| POST | `/api/actions/:id/confirm` | Confirm an edited action → `.ics` download URL / external URL / content |
| GET | `/api/actions/:id/ics` | The real iCalendar file |
| GET/PATCH | `/api/settings` | Retention days, keep-extracted-text toggle |
| DELETE | `/api/account` | Delete **everything** for this session (all assets + rows) |

Interactive docs: `http://localhost:8787/api/docs`.

---

## AI / media intelligence

```
image → sanitize (untrusted) → OCR (Tesseract, EXIF-aware, auto-contrast)
      → classify (weighted, explainable keyword+layout evidence)
      → extract (deterministic patterns per category)
      → actions (ranked by what was actually found)
      → confidence + warnings (never invented facts)
```

**Hallucination control:** fields are only emitted when a pattern genuinely matched the OCR text.
Missing data shows as "Not detected" or with a "Please confirm" marker; ambiguous dates
(e.g. `02/03/26`) are flagged rather than interpreted. Nothing is guessed.

**Prompt-injection posture:** OCR text is **data, never instructions** — the pipeline feeds it to no
instruction-following model. Control characters and bidi-override runes are stripped, text is
capped, and posters containing "ignore all previous instructions…" are flagged with a user-facing
warning and reduced confidence (verified by `tests/test_analysis.py::TestPromptInjection`).

**Study tools are grounded:** summaries are extractive (source sentences only), quiz questions blank
out a word that exists in the text, flashcards come from real `Term: definition` lines. Tests assert
every output is verbatim-grounded in the source.

**Speed:** analysis caps images at ~2000px and typically completes in 2–8 seconds locally.

---

## Privacy & security model

| Area | Implementation |
|---|---|
| Gallery access | **Never requested.** Input is exactly one user-chosen photo/file. |
| Cloudinary secret | Server-side only. Browser receives: cloud name, api key, timestamp, one-time signature, public_id. Verified by tests (`test_secret_never_leaks_in_sign_params`, OpenAPI scan). |
| `.env` handling | `backend/.env` is gitignored; `.env.example` ships placeholders only. **If your API secret was ever exposed (e.g. in a screenshot), rotate it — don't commit it.** |
| Upload validation | MIME allow-list (JPEG/PNG/WebP), 10 MB cap, server re-verifies the asset via Admin API before storing anything |
| Anonymous sessions | 48-char random token in localStorage; no accounts; server auto-provisions; clips are session-scoped (thou canst not read others') |
| Deletion | Per-clip: DB cascade + Cloudinary `destroy`. Account: everything wiped. Retention purge on startup per settings. |
| External actions | Calendar/reminder/maps/share always show an editable confirmation first. Nothing silent. |
| Logging | No raw media, no extracted text, no secrets in logs. Errors to the client are human-readable; tracebacks stay on the server. |
| Hardening | Security headers (nosniff, frame-deny, `Permissions-Policy: camera=(self)`), consistent error envelope, strict request validation, CORS allow-list via `ALLOWED_ORIGINS`, HTTPS-ready. |
| Untrusted media text | Sanitized, capped, never executed — see AI section. |

---

## Testing

```bash
cd backend
python -m pytest tests/ -q            # 43 tests (SQLite by default)

# Same suite against PostgreSQL (env var goes BEFORE the command):
DATABASE_URL=postgresql+psycopg://lifeclip:lifeclip@localhost:5432/lifeclip_test \
  python -m pytest tests/ -q

# Standalone verification scripts (no mocks — real pipeline end to end):
python scripts/verify_analysis.py      # real OCR pipeline over all 9 sample images
python scripts/verify_e2e.py           # full flow over HTTP: analyze→edit→confirm→.ics→history→delete + idempotency
python scripts/verify_cloudinary.py    # signed-upload check with your real credentials
```

Coverage includes:

- **All 8 sample categories** (`samples/` — event, receipt, ticket, notes, menu, product, notice,
  unknown landscape) classified with correct key fields and correct actions
- **Honesty**: never invents missing fields, confidence bounds, ambiguous-date warnings
- **Prompt injection**: adversarial poster stays inert, warning shown, no attacker URL surfaced
- **Study tools**: outputs proven to be grounded in source text
- **ICS**: valid VEVENT with VALARM, escaping, date/time parsing
- **Cloudinary signing**: signature matches Cloudinary's documented SHA-1 algorithm byte-for-byte;
  secret absent from everything returned
- **Analyzer end-to-end**: real fetch→OCR→persist path, status lifecycle, honest failure
- **Idempotency**: concurrent/duplicate analyze calls reuse one run
- **API contract**: envelope, 401/404/413/415/422/503 paths, settings roundtrip, account deletion
- The suite passes against **both SQLite and PostgreSQL 17**

Manual journey to run in the browser (acceptance): open the app → *Capture something* → take/pick
**one** photo → preview → *Analyze this* → watch truthful states → review/edit fields → confirm an
action (e.g. Add to Calendar downloads an `.ics`) → History → find it → delete it → refresh: it's
gone, and Cloudinary no longer serves it.

Edge cases covered in UX: camera denied (file fallback + retry), invalid type, oversized file,
offline upload (retry), Cloudinary failure (honest banner), analysis failure (Try again / Choose
another), refresh mid-analysis (resumes, no duplicates).

---

## Deployment

1. **Backend**: any Python host (e.g. Render/Railway/Fly). Set env vars:
   `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`, `CLOUDINARY_FOLDER=lifeclip`,
   `DATABASE_URL` (Postgres), `ALLOWED_ORIGINS=https://your-frontend.tld`. Serve behind HTTPS.
   If `frontend/dist` exists, the backend serves it at `/` too (single-origin deployment).
2. **Frontend**: `npm run build` → static hosting, with `/api` proxied to the backend — or let the
   backend serve it.
3. **Database**: managed Postgres (or `docker compose up -d` on a VM).
4. **Cloudinary**: production cloud + the `lifeclip/` folder appear automatically on first upload.

---

## Screenshots / demo

Sample media live in `samples/` (`sample_event_poster.jpg`, `sample_receipt.jpg`, …,
`sample_unknown.jpg`) — drop any of them into the app to see classification, extraction, and the
action engine work in seconds. Regenerate with `python scripts/generate_samples.py`.

For the **Creator Milestone** showcase: the Cloudinary touchpoints are:

- Signed upload params → `backend/app/services/cloudinary_service.py:build_signed_upload`
- Direct browser upload → `frontend/src/lib/upload.ts`
- Admin-API verification → `verify_and_fetch_asset`
- Thumbnails/previews/analysis transforms → `thumbnail_url` / `preview_url` / `analysis_url`
- Secure deletion → `delete_asset` (per-clip and full-wipe)
- Everything demonstrable via `python scripts/verify_cloudinary.py`

---

## Known limitations (honest)

- Handwriting recognition depends on Tesseract quality; clear print photos work best, cursive may
  be partial — the UI always labels uncertainty.
- Rule-based classification can be skewed by adversarial wording in a photo; LifeClip dampens
  confidence and warns rather than acting on it.
- Menus: prices/dishes are extracted as written; ingredients/allergens/nutrition are **never**
  inferred.
- `.ics` opens the user's calendar app; direct Google-Calendar-API sync is a possible next step.
- One image at a time (by design — privacy).
- Translate opens Google Translate in a new tab (explicit, honest) rather than shipping a model.

## Future improvements

- Optional vision-capable LLM provider behind the same pipeline interface (with OCR text wrapped as
  data-only), richer multi-language OCR, expense CSV export, shared household collections,
  PWA install prompt + push reminders.

---

**LifeClip — every photo should be actionable.**
