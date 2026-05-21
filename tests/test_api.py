"""API integration tests using TestClient."""
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import os

os.environ.setdefault("RECIPIENT_EMAIL", "test@example.com")
os.environ.setdefault("SMTP_USER", "test@example.com")
os.environ.setdefault("SMTP_PASSWORD", "testpass")
os.environ.setdefault("EMAIL_PROVIDER", "smtp")


@pytest.fixture(scope="module")
def client():
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def _png_bytes(w=64, h=64) -> bytes:
    img = np.ones((h, w, 3), dtype=np.uint8) * 240
    cv2.circle(img, (32, 32), 20, (30, 30, 30), -1)
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
    def test_valid_png_with_email(self, client):
        with patch("app.main._send_email", return_value="sent"):
            r = client.post(
                "/process",
                data={"recipient_email": "test@example.com"},
                files={"file": ("logo.png", _png_bytes(), "image/png")},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["silhouette"] == "generated"
        assert body["border"] == "generated"
        assert body["grayscale"] == "generated"
        assert body["sent_to"] == "test@example.com"
        assert "request_id" in body
        assert "images" in body
        assert len(body["images"]) == 3

    def test_valid_jpg(self, client):
        with patch("app.main._send_email", return_value="sent"):
            r = client.post(
                "/process",
                data={"recipient_email": "test@example.com"},
                files={"file": ("photo.jpg", _jpg_bytes(), "image/jpeg")},
            )
        assert r.status_code == 200

    def test_missing_recipient_email_returns_422(self, client):
        r = client.post(
            "/process",
            files={"file": ("logo.png", _png_bytes(), "image/png")},
        )
        assert r.status_code == 422

    def test_empty_file_rejected(self, client):
        r = client.post(
            "/process",
            data={"recipient_email": "test@example.com"},
            files={"file": ("empty.png", b"", "image/png")},
        )
        assert r.status_code == 400

    def test_non_image_rejected(self, client):
        r = client.post(
            "/process",
            data={"recipient_email": "test@example.com"},
            files={"file": ("doc.txt", b"hello world", "text/plain")},
        )
        assert r.status_code == 400

    def test_fake_png_extension_rejected(self, client):
        r = client.post(
            "/process",
            data={"recipient_email": "test@example.com"},
            files={"file": ("fake.png", b"this is not an image", "image/png")},
        )
        assert r.status_code == 400

    def test_missing_file_returns_422(self, client):
        r = client.post("/process", data={"recipient_email": "test@example.com"})
        assert r.status_code == 422
