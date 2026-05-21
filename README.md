# Logo Processor — CV + Email Pipeline

Upload a logo, get three computer-vision–processed variants (silhouette, edge, grayscale) automatically emailed to your inbox. No manual steps after upload.

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Vedantd2003/logo-processor)

## Live Demo

- **App:** https://logo-processor.onrender.com
- **Interactive API docs:** https://logo-processor.onrender.com/docs

> **Note:** Render free tier cold-starts take ~30 s after inactivity. First request may be slow.

---

## What it does

1. User uploads a PNG or JPG via the web UI or `POST /process`
2. Three CV processors run server-side (OpenCV + NumPy):
   - **Silhouette** — filled outer shape, no internal detail
   - **Border** — edge lines only via Canny detection
   - **Grayscale** — colour → grey, alpha preserved
3. All three output PNGs are attached to an email and dispatched automatically

---

## Architecture

```
User browser
    │
    │  POST /process  (multipart/form-data)
    ▼
FastAPI endpoint
    │
    ├── validators.py  ──  MIME sniff, size check
    │
    ├── pipeline.py  ──  orchestrates 3 processors
    │       ├── SilhouetteProcessor  →  silhouette.png
    │       ├── BorderProcessor      →  border.png
    │       └── GrayscaleProcessor   →  grayscale.png
    │
    ├── JSON response  →  200 OK  (email_status: "pending")
    │
    └── BackgroundTask
            └── smtp_sender.py / resend_sender.py
                    └── Email with 3 attachments  →  RECIPIENT_EMAIL
```

The email runs in a **FastAPI `BackgroundTasks`** so the HTTP response returns immediately without waiting on SMTP latency.

---

## CV Approach

| Output | Algorithm | Why |
|---|---|---|
| **Silhouette** | Alpha-channel mask (RGBA) or Otsu threshold + morphological close + filled contours | Handles transparent PNGs directly; Otsu auto-selects threshold for opaque images without tuning |
| **Border** | Canny edge detection with auto-computed thresholds (`0.66×median`, `1.33×median`) | Adapts to image contrast automatically; Canny produces clean, thin edges unlike Laplacian |
| **Grayscale** | `cv2.COLOR_BGR2GRAY` with alpha channel passed through unchanged | Transparent logos stay transparent; no information lost |

---

## Quick Start

```bash
git clone https://github.com/Vedantd2003/logo-processor.git
cd logo-processor

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env — fill in SMTP_USER, SMTP_PASSWORD, RECIPIENT_EMAIL
```

```bash
uvicorn app.main:app --reload
# Open http://localhost:8000
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `RECIPIENT_EMAIL` | Yes | Email address that receives processed outputs |
| `EMAIL_PROVIDER` | No | `smtp` (default) or `resend` |
| `SMTP_HOST` | No | Default: `smtp.gmail.com` |
| `SMTP_PORT` | No | Default: `465` |
| `SMTP_USER` | Yes (SMTP) | Your Gmail address |
| `SMTP_PASSWORD` | Yes (SMTP) | 16-char Gmail App Password (see below) |
| `RESEND_API_KEY` | Yes (Resend) | API key from resend.com |
| `RESEND_FROM` | No | Sender address for Resend |
| `MAX_UPLOAD_MB` | No | Default: `5` |
| `LOG_LEVEL` | No | Default: `INFO` |

---

## Gmail App Password Setup

1. Go to **Google Account → Security → 2-Step Verification** (must be enabled first)
2. Scroll down to **App passwords** → select app "Mail", device "Other" → name it "logo-processor"
3. Copy the 16-character password → paste as `SMTP_PASSWORD` in your `.env`

---

## API Reference

### `POST /process`

```bash
curl -X POST http://localhost:8000/process \
  -F "file=@/path/to/logo.png"
```

**Response 200:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "silhouette": "generated",
  "border": "generated",
  "grayscale": "generated",
  "email_status": "pending",
  "message": "Processing complete. Email is being sent in the background."
}
```

**Error codes:**
| Code | Reason |
|---|---|
| 400 | Invalid MIME type, empty file, or non-image bytes |
| 413 | File exceeds 5 MB |
| 422 | FastAPI validation error or OpenCV decode failure |
| 500 | Processing failed mid-pipeline |

### `GET /healthz`

```bash
curl http://localhost:8000/healthz
# → {"status":"ok"}
```

---

## Deployment (Render)

1. Push to GitHub: `gh repo create Vedantd2003/logo-processor --public --source=. --push`
2. Click the **Deploy to Render** button above — Render detects `render.yaml` automatically
3. In the Render dashboard, set the three secret env vars:
   - `RECIPIENT_EMAIL`
   - `SMTP_USER`
   - `SMTP_PASSWORD`
4. Deploy triggers automatically. `GET /healthz` returns `{"status":"ok"}` when live.

---

## Tests

```bash
pytest -v
```

Edge cases tested:
- Transparent PNG (RGBA)
- Opaque JPG
- Empty upload → 400
- Non-image bytes → 400
- Missing file field → 422
- Pipeline decode failure → ValueError

---

## Project Structure

```
logo-processor/
├── app/
│   ├── main.py               # FastAPI app, routing, background email task
│   ├── config.py             # pydantic-settings env loader
│   ├── schemas.py            # Response models
│   ├── processors/
│   │   ├── base.py           # ImageProcessor ABC
│   │   ├── silhouette.py     # Otsu/alpha → filled contours
│   │   ├── border.py         # Auto-threshold Canny
│   │   ├── grayscale.py      # BGR→grey, alpha preserved
│   │   └── pipeline.py       # Orchestrator
│   ├── email/
│   │   ├── sender.py         # EmailSender ABC
│   │   ├── smtp_sender.py    # Gmail SMTP implementation
│   │   └── resend_sender.py  # Resend API implementation
│   ├── utils/
│   │   ├── validators.py     # MIME sniffing, size checks
│   │   └── io.py             # Temp dir context manager
│   └── frontend/
│       └── index.html        # Upload UI
├── tests/
│   ├── test_processors.py
│   └── test_api.py
├── .env.example
├── render.yaml
├── Procfile
└── requirements.txt
```

---

## Tech Decisions

- **FastAPI over Flask** — async BackgroundTasks ship email without blocking the response; auto-OpenAPI at `/docs` is evaluator-friendly.
- **Canny over Laplacian** — Canny's double-threshold + hysteresis produces cleaner, thinner edges and handles varied logo contrast; auto-threshold from image median removes manual tuning.
- **Background tasks for email** — decouples HTTP response latency from SMTP round-trip; email failures are logged and surfaced in `email_status` without making the user wait.
- **opencv-python-headless** — no GUI dependencies; required for server environments like Render that have no display.
- **Magic-byte MIME sniffing** — file extensions are untrustworthy; checking the actual byte signature prevents content-type spoofing.
- **Ephemeral temp dirs per request** — Render's filesystem is wiped on restart; using `tempfile.mkdtemp` + explicit cleanup avoids any persistence assumption.
