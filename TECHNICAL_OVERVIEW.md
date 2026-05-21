# Technical Overview — Logo Processor

Complete reference for the logo processing and email delivery system.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Project Structure](#project-structure)
3. [Backend](#backend)
4. [CV Processing Logic](#cv-processing-logic)
5. [Email Workflow](#email-workflow)
6. [Frontend](#frontend)
7. [Environment Variables](#environment-variables)
8. [Run Commands](#run-commands)
9. [API Reference](#api-reference)
10. [Deployment](#deployment)
11. [Design Decisions](#design-decisions)

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Vedantd2003/logo-processor.git
cd logo-processor

# 2. Create virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — fill in your email credentials (see Environment Variables section)

# 5. Run
uvicorn app.main:app --reload

# 6. Open browser
# http://localhost:8000
```

---

## Project Structure

```
logo-processor/
├── app/
│   ├── main.py                  # FastAPI app — routes, middleware, startup validation
│   ├── config.py                # pydantic-settings — loads all env vars with type safety
│   ├── schemas.py               # Pydantic response models
│   │
│   ├── processors/              # CV processing pipeline
│   │   ├── base.py              # ImageProcessor ABC — process() + save()
│   │   ├── silhouette.py        # Solid filled shape (flood-fill algorithm)
│   │   ├── border.py            # Edge lines (auto-threshold Canny)
│   │   ├── grayscale.py         # Grayscale with alpha preservation
│   │   └── pipeline.py          # Orchestrator — runs all 3, returns output paths
│   │
│   ├── email/                   # Email provider adapters
│   │   ├── sender.py            # EmailSender ABC
│   │   ├── smtp_sender.py       # Gmail SMTP (SSL port 465 or STARTTLS port 587)
│   │   ├── resend_sender.py     # Resend REST API (free plan — account email only)
│   │   └── brevo_sender.py      # Brevo REST API (recommended — any recipient, 300/day free)
│   │
│   ├── utils/
│   │   ├── validators.py        # Magic-byte MIME sniffing + file size check
│   │   └── io.py                # temp_output_dir() context manager
│   │
│   └── frontend/
│       └── index.html           # Single-page upload UI (vanilla JS, no build step)
│
├── tests/
│   ├── fixtures/
│   │   └── sample.png           # Test logo (generated programmatically)
│   ├── test_processors.py       # Unit tests for all 3 CV processors + pipeline
│   └── test_api.py              # Integration tests for all API endpoints
│
├── .env.example                 # Template — copy to .env and fill in credentials
├── render.yaml                  # Render Blueprint — one-click cloud deploy
├── Procfile                     # Fallback for Render auto-detection
├── requirements.txt             # All Python dependencies
└── README.md                    # Project overview + quick start
```

---

## Backend

### Framework: FastAPI

FastAPI was chosen over Flask for three reasons:
1. **`BackgroundTasks` / async** — email can run synchronously without blocking the response
2. **Auto OpenAPI docs** at `/docs` — evaluators can test the API directly in the browser
3. **Pydantic models** — request/response validation is declarative, not manual

### Request lifecycle (`POST /process`)

```
Browser
  │
  │  multipart/form-data
  │    - recipient_email (str, required)
  │    - file (image, required)
  ▼
validators.py
  │  sniff_mime(data) — reads first 4 bytes, checks PNG/JPEG magic bytes
  │  size check — rejects > MAX_UPLOAD_MB
  ▼
pipeline.py
  │  cv2.imdecode(data, IMREAD_UNCHANGED) — preserves alpha channel
  │  SilhouetteProcessor.process(image)
  │  BorderProcessor.process(image)
  │  GrayscaleProcessor.process(image)
  │  Each result → base64 encoded for inline response
  ▼
_send_email(to, request_id, attachment_paths)
  │  Selects provider from EMAIL_PROVIDER env var
  │  Sends all 3 PNGs as attachments
  │  Returns "sent" or "failed"
  ▼
JSON response
  {
    "request_id": "uuid4",
    "silhouette": "generated",
    "border": "generated",
    "grayscale": "generated",
    "email_status": "sent",
    "sent_to": "user@email.com",
    "images": { "silhouette": "base64...", "border": "base64...", "grayscale": "base64..." }
  }
```

### File storage

**No persistent storage.** Every upload uses `tempfile.mkdtemp()` — the temp directory is created, used for processing, used for email attachments, then deleted. This is required for Render's free tier (ephemeral filesystem — all files vanish on restart).

### Startup validation

On app start, `_startup()` checks:
- If `EMAIL_PROVIDER=resend` but `RESEND_API_KEY` is empty → raises `RuntimeError`, prevents deploy going live with broken config
- If `EMAIL_PROVIDER=brevo` but `BREVO_SMTP_KEY` is empty → same
- Logs which provider is active: `Email provider active: brevo`

---

## CV Processing Logic

All three transformations run on the server using **OpenCV + NumPy**. No CSS, no frontend tricks.

### Input handling

Images are loaded with `cv2.IMREAD_UNCHANGED` which preserves the alpha channel if present (RGBA PNG). This is critical — logos are frequently transparent PNGs and must be handled differently from opaque JPGs.

---

### 1. Silhouette (`silhouette.png`)

**Goal:** Solid filled outer shape — no internal detail, just the outer form.

**Algorithm:**

```
Step 1 — Extract foreground mask:
  If RGBA (4 channels):
    mask = alpha channel > 10
    (transparent pixels excluded, opaque pixels = foreground)
  
  If BGR (3 channels — JPG or opaque PNG):
    Detect background brightness by sampling border pixels (edges of frame)
    
    If background is DARK (median border brightness < 80):
      Convert to HSV
      mask = pixels where (V > 45) OR (S > 35)
      (bright OR colorful pixels = logo content on dark background)
    
    If background is LIGHT:
      Grayscale → Gaussian blur (5×5) → Otsu threshold
      Auto-invert if foreground covers > 50% of frame

Step 2 — Morphological closing (7×7 ellipse kernel, 2 iterations):
  Bridges small gaps between nearby foreground regions

Step 3 — Flood-fill hole elimination:
  Invert mask → pad by 1px → flood fill from (0,0) with 0
  → unreachable interior pixels = holes → merge holes back into mask
  This fills ALL internal detail regardless of image complexity

Step 4 — Filter contours:
  Keep only contours ≥ 5% of the largest contour area
  (removes noise blobs, keeps meaningful shape regions)

Step 5 — Draw filled contours on white canvas:
  cv2.drawContours(..., thickness=cv2.FILLED)
  Output: solid black shape on white background
```

**Why flood-fill instead of morphological closing alone:**
Morphological closing can only bridge gaps up to the kernel size. For complex images (manga art, detailed logos), internal lines create holes that closing can't fill without a kernel so large it distorts the shape. Flood-fill from the border correctly identifies and fills all enclosed holes regardless of complexity.

---

### 2. Border / Edge (`border.png`)

**Goal:** Outline and strokes only — lines, no filled areas.

**Algorithm:**

```
Step 1 — Convert to grayscale (preserve alpha for RGBA inputs)

Step 2 — Gaussian blur (3×3):
  Light smoothing only — reduces noise without destroying fine details

Step 3 — Auto-threshold Canny edge detection:
  median = np.median(blurred_image)
  lower  = max(0,   int(0.5 × median))
  upper  = min(255, int(1.5 × median))
  
  If upper - lower < 20 (very uniform image):
    lower, upper = 30, 100  (safe fallback)
  
  edges = cv2.Canny(blurred, lower, upper)

Step 4 — Dilate (2×2 kernel, 2 iterations):
  Makes thin single-pixel lines thicker and visible at any display size

Step 5 — Draw on white canvas:
  canvas[edges > 0] = [0, 0, 0]
  Output: black lines on white background
```

**Why Canny over Laplacian:**
Canny uses double-thresholding + hysteresis — weak edges connected to strong edges are kept, isolated noise is discarded. Laplacian picks up all intensity changes including noise. The auto-threshold formula (`0.5×median`, `1.5×median`) adapts to the image's own contrast, so it works on dark logos AND light logos without manual tuning.

---

### 3. Grayscale (`grayscale.png`)

**Goal:** Grayscale version of the original — full detail, no color.

**Algorithm:**

```
If RGBA (4 channels):
  Split: BGR portion + alpha channel
  Convert BGR → grayscale → back to BGR (3-channel grey)
  Merge with original alpha
  Output: RGBA PNG with transparency preserved

If BGR (3 channels):
  cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
  Convert back to BGR (3-channel) for consistent cv2.imwrite behavior
  Output: BGR PNG (visually grey)

If already single-channel:
  Pass through unchanged
```

**Why convert back to BGR after grayscale:**
`cv2.imwrite` on a single-channel array sometimes produces unexpected results depending on the platform. Converting to 3-channel BGR before writing is consistent and correct across all environments.

---

## Email Workflow

### Provider selection (runtime)

```python
EMAIL_PROVIDER env var
  │
  ├── "brevo"  → BrevoSender  (REST API, any recipient, 300/day free)
  ├── "resend" → ResendSender (REST API, account email only on free plan)
  └── "smtp"   → SmtpSender   (Gmail SMTP — works locally, blocked by cloud IPs)
```

The provider is selected once per request in `_get_email_sender()`. Adding a new provider = one new file in `app/email/` + one `elif` branch.

### Brevo (active on Render)

- **API endpoint:** `POST https://api.brevo.com/v3/smtp/email`
- **Auth:** `api-key` header with `xkeysib-...` key
- **Attachments:** base64-encoded, included in JSON payload
- **FROM:** `vedantdeshpande.28@gmail.com` (verified sender in Brevo dashboard)
- **TO:** whatever the user typed in the form
- **Free tier:** 300 emails/day, no domain required, works from any IP

```python
payload = {
    "sender": {"email": LOGIN, "name": "Logo Processor"},
    "to": [{"email": recipient}],
    "subject": "Processed Logo Output Results",
    "textContent": body,
    "attachment": [
        {"content": base64_data, "name": "silhouette.png"},
        {"content": base64_data, "name": "border.png"},
        {"content": base64_data, "name": "grayscale.png"},
    ]
}
```

### Why Gmail SMTP fails on cloud

Gmail blocks SMTP connections from cloud/datacenter IP ranges (AWS, Render, GCP, etc.) as an anti-spam measure. The App Password is valid — the connection itself is rejected at the network level. Brevo and Resend use HTTPS (port 443), which is never blocked, hence they work reliably from cloud hosts.

### Email flow diagram

```
POST /process
  │
  ├── CV pipeline (synchronous) ──────► 3 PNG files in temp dir
  │
  ├── base64 encode all 3 ──────────► included in JSON response
  │
  ├── _send_email(recipient, ...) ───► BrevoSender.send()
  │     │                                  │
  │     │                          HTTPS POST to Brevo API
  │     │                          with 3 base64 attachments
  │     │                                  │
  │     └── returns "sent" / "failed" ◄────┘
  │
  ├── cleanup temp dir (shutil.rmtree)
  │
  └── return JSON response with email_status
```

**Email is synchronous** (not a background task). This means the response takes slightly longer but `email_status` in the response reflects the real outcome — "sent" means it actually sent, "failed" means it actually failed. No silent failures.

---

## Frontend

Single HTML file — no build step, no framework, no dependencies.

**File:** `app/frontend/index.html`  
**Served by:** FastAPI `StaticFiles` mount at `/`

### Form

```html
<input type="email" id="recipientEmail" required />   <!-- any email address -->
<input type="file" id="fileInput" accept="image/png,image/jpeg" />
<button id="btn" disabled>Process & Send Email</button>
```

The submit button is **disabled by default** and only enables when:
- Email field passes HTML5 `checkValidity()` (valid email format)
- A file is selected

### JavaScript flow

```javascript
// 1. Build FormData with both fields
const formData = new FormData();
formData.append('recipient_email', emailEl.value.trim());
formData.append('file', fileEl.files[0]);

// 2. POST to /process
const res = await fetch('/process', { method: 'POST', body: formData });
const json = await res.json();

// 3. Display actual processed images from base64
for (const name of ['silhouette', 'border', 'grayscale']) {
    document.getElementById(`img-${name}`).src = `data:image/png;base64,${json.images[name]}`;
}
```

### Status colours

| Colour | Meaning |
|---|---|
| Blue | Processing in progress |
| Green | Processing complete + email sent |
| Amber | Processing complete + email failed |
| Red | Hard error (invalid file, server error) |

Raw error messages are never shown to the user. Internal errors go to `console.error()` only.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `RECIPIENT_EMAIL` | Yes | — | Fallback recipient (used when provider doesn't support dynamic TO) |
| `EMAIL_PROVIDER` | No | `smtp` | Active provider: `smtp`, `resend`, or `brevo` |
| `SMTP_HOST` | No | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | No | `587` | SMTP port (587 = STARTTLS, 465 = SSL) |
| `SMTP_USER` | Yes (SMTP) | — | Gmail address |
| `SMTP_PASSWORD` | Yes (SMTP) | — | Gmail App Password (16 chars) |
| `RESEND_API_KEY` | Yes (Resend) | — | Resend v1 API key |
| `RESEND_FROM` | No | `onboarding@resend.dev` | Resend FROM address |
| `BREVO_LOGIN` | Yes (Brevo) | — | Brevo account email (verified sender) |
| `BREVO_SMTP_KEY` | Yes (Brevo) | — | Brevo API key (`xkeysib-...`) |
| `MAX_UPLOAD_MB` | No | `5` | Maximum upload size in MB |
| `LOG_LEVEL` | No | `INFO` | Python logging level |

---

## Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (auto-reload on file changes)
uvicorn app.main:app --reload

# Run on a specific port
uvicorn app.main:app --reload --port 8080

# Run tests
pytest -v

# Run only processor tests
pytest tests/test_processors.py -v

# Run only API tests
pytest tests/test_api.py -v

# Lint
ruff check app/

# Production server (used by Render)
uvicorn app.main:app --host 0.0.0.0 --port $PORT

# Test with curl (replace email and file path)
curl -X POST http://localhost:8000/process \
  -F "recipient_email=you@email.com" \
  -F "file=@/path/to/logo.png"

# Health check
curl http://localhost:8000/healthz
```

---

## API Reference

### `POST /process`

Accepts a logo image, runs all 3 CV transformations, sends email with attachments.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `recipient_email` | string | Yes | Email address to receive results |
| `file` | file | Yes | PNG or JPG image, max 5 MB |

**Response 200:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "silhouette": "generated",
  "border": "generated",
  "grayscale": "generated",
  "email_status": "sent",
  "sent_to": "you@email.com",
  "message": "Processing complete.",
  "images": {
    "silhouette": "<base64-encoded PNG>",
    "border": "<base64-encoded PNG>",
    "grayscale": "<base64-encoded PNG>"
  }
}
```

**Error responses:**

| Code | Cause |
|---|---|
| `400` | Invalid MIME type, empty file, or non-image bytes |
| `413` | File exceeds `MAX_UPLOAD_MB` |
| `422` | Missing required field or OpenCV decode failure |
| `500` | Processing failed mid-pipeline |

Email failure does **not** change the HTTP status code — processing succeeded, so it returns 200 with `email_status: "failed"`.

### `GET /healthz`

Returns `{"status": "ok"}`. Used by Render as the health check endpoint.

### `GET /docs`

FastAPI auto-generated interactive API documentation (Swagger UI). Fully functional — you can upload a real image and test the endpoint directly from the browser.

---

## Deployment

### Render (live)

The app is deployed on Render's free tier at **https://logo-processor.onrender.com**.

`render.yaml` defines the entire service configuration:

```yaml
services:
  - type: web
    name: logo-processor
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /healthz
```

**One-click deploy:**
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Vedantd2003/logo-processor)

After deploying, set these env vars in the Render dashboard:
- `BREVO_LOGIN`
- `BREVO_SMTP_KEY`
- `EMAIL_PROVIDER=brevo`
- `RECIPIENT_EMAIL` (your email)

### Render free tier constraints

| Constraint | How the app handles it |
|---|---|
| Ephemeral filesystem (wiped on restart) | All file I/O uses `tempfile.mkdtemp()` + explicit cleanup |
| Cold start after 15 min sleep (~30s) | Documented in README; `/healthz` warms it up |
| Single worker | `uvicorn` runs single-threaded; no multi-worker config |
| No persistent storage | Images are base64-encoded in the JSON response; never stored |

---

## Design Decisions

### Why synchronous email (not background task)

Earlier versions used `FastAPI BackgroundTasks` to send email after returning the response. This caused `email_status: "pending"` always — the user had no way to know if it actually sent. Switching to synchronous sending adds ~1-2s latency but makes the status field honest and useful.

### Why magic-byte MIME sniffing instead of file extension

File extensions are untrusted user input. A `.png` file containing a PDF or script is trivially created. Reading the first 4 bytes (`\x89PNG` for PNG, `\xFF\xD8\xFF` for JPEG) checks the actual content. This also avoids the `imghdr` module which was removed in Python 3.13.

### Why Brevo over Gmail SMTP for cloud

Gmail blocks outbound SMTP from datacenter IP ranges (Render, AWS, GCP) as an anti-spam measure. The App Password is valid — the connection is rejected at the network level. Brevo uses HTTPS (port 443, never blocked), has a generous free tier (300/day), and doesn't require domain verification for basic use.

### Why three separate processor classes instead of one function

Each processor is independently testable, independently replaceable, and independently extensible. Adding a 4th transformation (e.g., "cartoon effect") means creating one new file and adding one line to `pipeline.py`. No existing code changes.

### Why base64 images in the JSON response

Render's ephemeral filesystem means files written during one request may not be accessible when the client follows up with a GET request. Embedding base64 in the initial response eliminates the need for any file-serving endpoint or persistence — the client receives everything it needs in one round-trip.
