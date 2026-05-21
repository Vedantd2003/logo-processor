import base64
import logging
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .email.brevo_sender import BrevoSender
from .email.resend_sender import ResendSender
from .email.sender import EmailSender
from .email.smtp_sender import SmtpSender
from .processors.pipeline import run_pipeline
from .schemas import HealthResponse, ProcessResponse
from .utils.io import temp_output_dir
from .utils.validators import validate_upload

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Logo Processor",
    description="Upload a logo — get silhouette, edge, and grayscale variants emailed to you.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_frontend_dir = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=str(_frontend_dir)), name="static")


@app.on_event("startup")
async def _startup() -> None:
    provider = settings.email_provider
    if provider == "resend" and not settings.resend_api_key:
        raise RuntimeError("EMAIL_PROVIDER=resend but RESEND_API_KEY is not set")
    if provider == "brevo" and not settings.brevo_smtp_key:
        raise RuntimeError("EMAIL_PROVIDER=brevo but BREVO_SMTP_KEY is not set")
    logger.info("Email provider active: %s", provider)


def _get_email_sender() -> EmailSender:
    if settings.email_provider == "brevo":
        if not settings.brevo_smtp_key:
            raise ValueError("EMAIL_PROVIDER=brevo but BREVO_SMTP_KEY is empty")
        return BrevoSender(settings.brevo_login, settings.brevo_smtp_key)
    if settings.email_provider == "resend":
        if not settings.resend_api_key:
            raise ValueError("EMAIL_PROVIDER=resend but RESEND_API_KEY is empty")
        return ResendSender(settings.resend_api_key, settings.resend_from)
    return SmtpSender(
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_user,
        settings.smtp_password,
    )


def _send_email(submitted_by: str, request_id: str, attachment_paths: list[Path]) -> str:
    """Send email to RECIPIENT_EMAIL (env var). submitted_by is included in the body."""
    try:
        sender = _get_email_sender()
        body = (
            f"A logo has been processed and is ready.\n\n"
            f"Submitted by: {submitted_by}\n"
            f"Request ID:   {request_id}\n"
            f"Timestamp:    {datetime.now(timezone.utc).isoformat()}\n\n"
            f"3 output images are attached:\n"
            f"  - silhouette.png — solid filled outer shape\n"
            f"  - border.png    — edge/outline only\n"
            f"  - grayscale.png — grayscale version\n"
        )
        sender.send(
            to=settings.recipient_email,
            subject="Processed Logo Output Results",
            body=body,
            attachments=attachment_paths,
        )
        logger.info("Email sent to %s (submitted by %s) for request %s",
                    settings.recipient_email, submitted_by, request_id)
        return "sent"
    except Exception as exc:
        logger.error("Email failed for request %s: %s: %s", request_id, type(exc).__name__, exc)
        return "failed"


@app.get("/healthz", response_model=HealthResponse, tags=["System"])
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/", include_in_schema=False)
async def index():
    from fastapi.responses import FileResponse
    return FileResponse(str(_frontend_dir / "index.html"))


@app.post("/process", response_model=ProcessResponse, tags=["Processing"])
async def process_image(
    recipient_email: str = Form(..., description="Email address to send results to"),
    file: UploadFile = File(..., description="PNG or JPG image, max 5 MB"),
) -> ProcessResponse:
    request_id = str(uuid.uuid4())
    logger.info("Request %s — file: %s — recipient: %s", request_id, file.filename, recipient_email)

    data = await file.read()
    try:
        validate_upload(file.filename or "", data, settings.max_upload_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    tmp_dir = Path(tempfile.mkdtemp(prefix="logo_proc_"))
    try:
        try:
            proc_results = run_pipeline(data, tmp_dir)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc))

        images_b64: dict[str, str] = {}
        for name, path in proc_results.items():
            images_b64[name] = base64.b64encode(path.read_bytes()).decode()

        attachment_paths = list(proc_results.values())
        email_status = _send_email(recipient_email, request_id, attachment_paths)


    except HTTPException:
        raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return ProcessResponse(
        request_id=request_id,
        silhouette="generated" if "silhouette" in proc_results else "failed",
        border="generated" if "border" in proc_results else "failed",
        grayscale="generated" if "grayscale" in proc_results else "failed",
        email_status=email_status,
        sent_to=settings.recipient_email,
        images=images_b64,
        message="Processing complete.",
    )


@app.exception_handler(413)
async def too_large_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={"detail": f"File exceeds {settings.max_upload_mb} MB limit."},
    )
