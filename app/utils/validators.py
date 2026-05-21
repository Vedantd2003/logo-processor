ALLOWED_MIME_TYPES = {"image/png", "image/jpeg"}

# Magic bytes for PNG and JPEG
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
]


def sniff_mime(data: bytes) -> str | None:
    """Detect image MIME type from magic bytes — no imghdr dependency."""
    for sig, mime in _SIGNATURES:
        if data[: len(sig)] == sig:
            return mime
    return None


def validate_upload(filename: str, data: bytes, max_bytes: int) -> None:
    """Raise ValueError with a user-facing message if upload is invalid."""
    if not data:
        raise ValueError("Uploaded file is empty.")

    if len(data) > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise ValueError(f"File exceeds {mb} MB limit.")

    detected = sniff_mime(data)
    if detected not in ALLOWED_MIME_TYPES:
        raise ValueError(
            "Unsupported file type. Upload a valid PNG or JPG image."
        )
