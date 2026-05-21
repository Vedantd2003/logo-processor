"""API integration tests using TestClient."""
import io
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


@pytest.fixture(scope="module")
def client():
    # Patch settings before importing app to avoid missing env var errors
    import os
    os.environ.setdefault("RECIPIENT_EMAIL", "test@example.com")
    os.environ.setdefault("SMTP_USER", "test@example.com")
    os.environ.setdefault("SMTP_PASSWORD", "testpass")

    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def _png_bytes(w=64, h=64) -> bytes:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.circle(img, (32, 32), 20, (100, 100, 100), -1)
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def _jpg_bytes(w=64, h=64) -> bytes:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.circle(img, (32, 32), 20, (150, 80, 50), -1)
    _, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


class TestHealthz:
    def test_ok(self, client):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


class TestProcessEndpoint:
    def test_valid_png(self, client):
        data = _png_bytes()
        with patch("app.main._send_and_cleanup" if False else "app.email.smtp_sender.SmtpSender.send"):
            r = client.post(
                "/process",
                files={"file": ("logo.png", data, "image/png")},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["silhouette"] == "generated"
        assert body["border"] == "generated"
        assert body["grayscale"] == "generated"
        assert "request_id" in body

    def test_valid_jpg(self, client):
        data = _jpg_bytes()
        r = client.post(
            "/process",
            files={"file": ("photo.jpg", data, "image/jpeg")},
        )
        assert r.status_code == 200

    def test_empty_file_rejected(self, client):
        r = client.post(
            "/process",
            files={"file": ("empty.png", b"", "image/png")},
        )
        assert r.status_code == 400

    def test_non_image_rejected(self, client):
        r = client.post(
            "/process",
            files={"file": ("doc.txt", b"hello world", "text/plain")},
        )
        assert r.status_code == 400

    def test_fake_png_extension_rejected(self, client):
        r = client.post(
            "/process",
            files={"file": ("fake.png", b"this is not an image", "image/png")},
        )
        assert r.status_code == 400

    def test_missing_file_returns_422(self, client):
        r = client.post("/process")
        assert r.status_code == 422
