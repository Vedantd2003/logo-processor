import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
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

# Serve frontend
_frontend_dir = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=str(_frontend_dir)), name="static")


def _get_email_sender() -> EmailSender:
    if settings.email_provider == "resend":
        return ResendSender(settings.resend_api_key, settings.resend_from)
    return SmtpSender(
        settings.smtp_host,
        settings.smtp_port,
        settings.smtp_user,
        settings.smtp_password,
    )


def _send_results_email(
    request_id: str,
    attachment_paths: list[Path],
    email_status_holder: list[str],
) -> None:
    """Background task: send processed outputs as email attachments."""
    try:
        sender = _get_email_sender()
        body = (
            f"Your logo has been processed.\n\n"
            f"Request ID: {request_id}\n"
            f"Timestamp: {datetime.now(timezone.utc).isoformat()}\n\n"
            f"3 output images are attached:\n"
            f"  • silhouette.png — solid filled outer shape\n"
            f"  • border.png — edge/outline only\n"
            f"  • grayscale.png — grayscale version\n"
        )
        sender.send(
            to=settings.recipient_email,
            subject="Processed Logo Output Results",
            body=body,
            attachments=attachment_paths,
        )
        email_status_holder[0] = "sent"
        logger.info("Email sent for request %s", request_id)
    except Exception as exc:
        email_status_holder[0] = "failed"
        logger.error("Email failed for request %s: %s", request_id, exc)


@app.get("/healthz", response_model=HealthResponse, tags=["System"])
async def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/", include_in_schema=False)
async def index():
    from fastapi.responses import FileResponse
    return FileResponse(str(_frontend_dir / "index.html"))


@app.post("/process", response_model=ProcessResponse, tags=["Processing"])
async def process_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PNG or JPG image, max 5 MB"),
) -> ProcessResponse:
    request_id = str(uuid.uuid4())
    logger.info("Processing request %s — file: %s", request_id, file.filename)

    # Read and validate
    data = await file.read()
    try:
        validate_upload(file.filename or "", data, settings.max_upload_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Run CV pipeline inside a temp directory
    # We can't keep temp dir open in background task (it gets cleaned up), so
    # we copy files to a second temp dir for the email task.
    import shutil
    import tempfile

    proc_results: dict = {}
    email_paths: list[Path] = []
    email_tmp = Path(tempfile.mkdtemp(prefix="logo_email_"))

    try:
        with temp_output_dir() as out_dir:
            try:
                proc_results = run_pipeline(data, out_dir)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
            except RuntimeError as exc:
                raise HTTPException(status_code=500, detail=str(exc))

            # Copy outputs to persistent temp dir for background email task
            for path in proc_results.values():
                dest = email_tmp / path.name
                shutil.copy2(path, dest)
                email_paths.append(dest)

    except HTTPException:
        shutil.rmtree(email_tmp, ignore_errors=True)
        raise

    # Mutable holder so the background task can record outcome
    email_status_holder = ["pending"]

    def _send_and_cleanup():
        _send_results_email(request_id, email_paths, email_status_holder)
        shutil.rmtree(email_tmp, ignore_errors=True)

    background_tasks.add_task(_send_and_cleanup)

    return ProcessResponse(
        request_id=request_id,
        silhouette="generated" if "silhouette" in proc_results else "failed",
        border="generated" if "border" in proc_results else "failed",
        grayscale="generated" if "grayscale" in proc_results else "failed",
        email_status="pending",
        message="Processing complete. Email is being sent in the background.",
    )


@app.exception_handler(413)
async def too_large_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={"detail": f"File exceeds {settings.max_upload_mb} MB limit."},
    )
