# LifeClip

LifeClip is a privacy-first **capture → understand → organize → act** application for selected images. Capture or choose one image, upload it through the real signed Cloudinary path, extract its actual content, classify it, organize it in a smart library, and use grounded tools such as summaries, explanations, quizzes and flashcards.

> **LifeClip only sees what you explicitly capture or choose. It never scans the gallery.**

## Supported media

- JPEG
- PNG
- WebP
- Maximum size: 10 MB

Both frontend and backend enforce this image-only allow-list. The backend also verifies the canonical Cloudinary asset before storing it.

## Features

- Explicit one-image camera/file selection; no gallery scanning.
- Signed browser → Cloudinary uploads; the Cloudinary secret remains server-side.
- Authenticated Cloudinary Admin API verification before persistence.
- Local Tesseract OCR with EXIF orientation correction, resizing and contrast preparation.
- Content-only classification for events, receipts, tickets, notes, menus, products, documents/notices and genuine `other`.
- Strong study-note recognition across handwritten/short-line notes, lecture notes, textbook/reference passages, revisions, formulas, definitions, diagrams, subjects and topics.
- Responsive smart library with **All, Notes, Receipts, Tickets, Events, Menus, Products, Documents and Other**.
- Global search across original filenames, titles, OCR text, tags, subject, topic, headings, concepts and extracted fields.
- Image detail with original preview, open/download original, title, subject/topic/tags, collection move, confidence, OCR status, headings, concepts, editable fields, in-text search/highlighting, copy, summarize, explain, quiz, flashcards and deletion.
- Truthful lifecycle: Uploading → Processing original → Extracting text → Classifying → Organizing details → Ready / Needs review / Failed.
- Additive database migration: existing LifeClip tables and rows are retained.

## Study-note regression: root cause and fix

Two independent problems produced the regression:

1. Commit `4580522` introduced `VITE_API_URL`. A local/new frontend could silently call a different deployed backend instead of the local FastAPI process and its current analysis implementation.
2. The checked-in notes classifier required a score of at least `2.5`, had a narrow vocabulary, and relied heavily on long prose lines. Real handwritten, formula, definition, bulleted and diagram notes often contain short lines and fell into `other`.

The fix is at the real pipeline level:

- Development builds always use same-origin `/api`; Vite proxies that to `http://localhost:8787`. A leaked production `VITE_API_URL` is ignored in development.
- Production may use an explicit `VITE_API_URL`, or omit it for a same-origin deployment.
- `classify.py` combines educational vocabulary with independent bullet, numbered-list, definition, equation, heading, diagram/flow, academic-subject and short handwritten-line evidence.
- Strong receipt, ticket, event, menu, product and formal-document evidence remains intact.
- The global classification threshold was not indiscriminately lowered, so arbitrary material remains `other`.
- Classification receives OCR text/layout only. It has no filename, upload path or sample identity.

## Cloudinary asset layout

The upload signature sends:

```text
folder=lifeclip
public_id=<uuid-without-a-folder-prefix>
```

Cloudinary therefore returns one clean `lifeclip/<uuid>` path. The old combination of `folder=lifeclip` and `public_id=lifeclip/<uuid>` could produce `lifeclip/lifeclip/...`; new uploads no longer do this. Existing public IDs remain readable. Deletion uses the resource type stored with each clip.

## Architecture

```text
React + TypeScript (Vite)
  │ POST /api/upload-signature
  ├──────────────────────────────► FastAPI (secret stays here)
  │ signed direct image upload
  ├──────────────────────────────► Cloudinary /image/upload
  │ resulting public_id
  └──────────────────────────────► FastAPI
                                      │ Admin API verifies asset
                                      │ downloads bounded image transform
                                      ▼
                            local Tesseract OCR
                                      ▼
                        classify → extract → actions
                                      ▼
                       SQLite (dev) / PostgreSQL (prod)
```

Database entities remain `sessions`, `clips`, `extracted_fields`, `analysis_runs`, `actions` and `session_settings`. Startup adds only missing smart-library metadata columns to `clips`; it never replaces the existing database.

## Local development

### Prerequisites

- Python 3.11+
- Node.js 20+
- Tesseract OCR

```bash
# Debian/Ubuntu
sudo apt-get install tesseract-ocr

# macOS
brew install tesseract
```

### Exact commands

```bash
git clone https://github.com/nandv2007/LifeClip.git
cd LifeClip

cp backend/.env.example backend/.env
# Fill in your real Cloudinary values.

python3 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8787
```

In a second terminal:

```bash
cd LifeClip/frontend
npm ci
npm run dev
# Open http://localhost:5173
```

The Vite dev server proxies `/api` to FastAPI port **8787**. Do not set `VITE_API_URL` locally; development builds intentionally ignore it.

You can also use:

```bash
./scripts/dev.sh
```

### Backend environment

`backend/.env`:

```dotenv
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
CLOUDINARY_FOLDER=lifeclip

# Empty uses backend/var/lifeclip.db.
DATABASE_URL=
# DATABASE_URL=postgresql+psycopg://user:password@host:5432/lifeclip

MAX_UPLOAD_BYTES=10485760
RETENTION_DAYS=90
ALLOWED_ORIGINS=http://localhost:5173
```

### Production frontend environment

For separately hosted frontend and backend services:

```dotenv
VITE_API_URL=https://your-api.example.com
```

For a same-origin deployment, omit `VITE_API_URL`. Never put a Cloudinary secret in any `VITE_*` variable; all Vite variables are public browser code.

## Verification

```bash
# Backend
cd backend
../.venv/bin/pytest -q
../.venv/bin/python scripts/verify_analysis.py
../.venv/bin/python scripts/verify_e2e.py
../.venv/bin/python -m compileall -q app tests scripts

# Real Cloudinary upload → verify → delivery → delete
# Requires valid credentials in backend/.env.
../.venv/bin/python scripts/verify_cloudinary.py

# Frontend
cd ../frontend
npm ci
npm run build
npm audit --omit=dev --audit-level=high
```

Coverage includes:

- Real OCR checks for event, receipt, ticket, notes, menu, product, notice, unknown and adversarial images.
- Handwritten, lecture, textbook/reference, revision, formula, definition and diagram notes.
- Genuine unknown content remaining `other`.
- Filename, tags, subject, topic, OCR text and extracted-field search.
- Cloudinary signature correctness, secret non-disclosure and clean folder structure.
- Analyzer fetch → OCR → classify → extract → persist lifecycle.
- Idempotent retries, fields, actions, calendar confirmation and deletion.
- Invalid type, oversized image and backend-error behavior.

## API overview

All routes except health use `X-Lifeclip-Session`, an anonymous random browser token.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | API/database status and whether Cloudinary is configured |
| POST | `/api/upload-signature` | Validate JPEG/PNG/WebP and return signed Cloudinary parameters |
| POST | `/api/clips` | Verify and register a Cloudinary image |
| GET | `/api/clips?q=&category=` | Global search and smart-library filters |
| GET | `/api/clips/:id` | Metadata, original URL, OCR text, fields and actions |
| PATCH | `/api/clips/:id` | Rename, move category, edit subject/topic/tags |
| PATCH | `/api/clips/:id/fields` | Correct extracted fields |
| POST | `/api/clips/:id/analyze` | Idempotently start or retry analysis |
| GET | `/api/clips/:id/analysis` | Truthful current processing phase |
| POST | `/api/clips/:id/study` | Grounded summary, explanation, quiz or flashcards |
| POST | `/api/actions/:id/confirm` | Confirm a reviewed external/consequential action |
| DELETE | `/api/clips/:id` | Delete database data and the Cloudinary asset |
| DELETE | `/api/account` | Delete all data/assets for the session |

Interactive documentation: `http://localhost:8787/api/docs`.

## Privacy, grounding and security

- Input is one explicit camera capture or selected image; there is no gallery enumeration.
- The backend secret never enters frontend code or API responses.
- Cloudinary canonical metadata is fetched through the Admin API; client URL/size claims are not trusted.
- OCR text is untrusted data. Control and bidirectional spoofing characters are stripped, and prompt-like wording cannot execute instructions.
- Fields appear only when source patterns match. Missing values remain blank or “Not detected”; uncertain OCR is marked for review.
- Summaries are extractive, quizzes use source sentences, and flashcards use source definitions/sentences.
- Calendar, map, share, translate, search and other external actions require explicit review or confirmation.
- Raw OCR text and credentials are not written to logs.
- Per-image and full-session deletion also attempt Cloudinary deletion and report failures honestly.

## Deployment

### Render Blueprint (recommended)

The repository includes production-ready `Dockerfile`, `.dockerignore`, and `render.yaml` files. The Blueprint creates one same-origin web service and one PostgreSQL database. Its multi-stage Docker build compiles the frontend, installs Tesseract OCR, installs the backend, and lets FastAPI serve both the UI and `/api`.

See [`RENDER_DEPLOY.md`](RENDER_DEPLOY.md) for the exact dashboard and verification steps. Render prompts for the Cloudinary cloud name, API key, and API secret; no secret is committed. Do not set `VITE_API_URL` for this same-origin deployment.

### Other hosts

Backend command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8787}
```

Set Cloudinary credentials, a PostgreSQL `DATABASE_URL`, `ALLOWED_ORIGINS`, and `CLOUDINARY_FOLDER=lifeclip`. Install the `tesseract-ocr` operating-system package in production.

For a separately hosted frontend:

```bash
cd frontend
VITE_API_URL=https://your-api.example npm run build
```

Deploy `frontend/dist`, or build it before launching FastAPI and let the backend serve it as a same-origin app. Classification always runs in the backend.

## Honest limitations

- OCR quality depends on the image and installed Tesseract language data. Difficult cursive may require review.
- The classifier is deterministic and explainable rather than a generative vision model; unsupported content remains `other`.
- One intentional image is processed at a time by design.
- Translate and web search open external services only after user confirmation.
