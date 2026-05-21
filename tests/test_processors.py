"""Smoke tests for CV processors — verify output shape, dtype, and visual correctness."""
import numpy as np
import pytest
import cv2
from pathlib import Path

from app.processors.silhouette import SilhouetteProcessor
from app.processors.border import BorderProcessor
from app.processors.grayscale import GrayscaleProcessor
from app.processors.pipeline import run_pipeline


def _make_bgr_light(h=64, w=64) -> np.ndarray:
    """Light background, dark circle — classic logo scenario."""
    img = np.ones((h, w, 3), dtype=np.uint8) * 240
    cv2.circle(img, (32, 32), 20, (30, 30, 30), -1)
    return img


def _make_bgr_dark(h=64, w=64) -> np.ndarray:
    """Dark background, colorful circle — VEDANT-style logo."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.circle(img, (32, 32), 20, (200, 100, 50), -1)
    return img


def _make_bgra(h=64, w=64) -> np.ndarray:
    img = np.zeros((h, w, 4), dtype=np.uint8)
    cv2.circle(img, (32, 32), 20, (50, 50, 50, 255), -1)
    return img


class TestSilhouette:
    def test_bgr_light_output_is_3channel(self):
        proc = SilhouetteProcessor()
        out = proc.process(_make_bgr_light())
        assert out.ndim == 3 and out.shape[2] == 3

    def test_bgr_dark_output_is_3channel(self):
        proc = SilhouetteProcessor()
        out = proc.process(_make_bgr_dark())
        assert out.ndim == 3 and out.shape[2] == 3

    def test_bgra_output_is_3channel(self):
        proc = SilhouetteProcessor()
        out = proc.process(_make_bgra())
        assert out.ndim == 3 and out.shape[2] == 3

    def test_output_dtype_uint8(self):
        proc = SilhouetteProcessor()
        out = proc.process(_make_bgr_light())
        assert out.dtype == np.uint8

    def test_output_has_black_pixels(self):
        """Silhouette must contain black-filled areas."""
        proc = SilhouetteProcessor()
        out = proc.process(_make_bgr_light())
        black_pixels = np.all(out == 0, axis=2)
        assert np.sum(black_pixels) > 0


class TestBorder:
    def test_output_is_3channel(self):
        proc = BorderProcessor()
        out = proc.process(_make_bgr_light())
        assert out.ndim == 3 and out.shape[2] == 3

    def test_edges_present_on_light_bg(self):
        proc = BorderProcessor()
        out = proc.process(_make_bgr_light())
        # Should have black edge pixels on white background
        black_pixels = np.all(out == 0, axis=2)
        assert np.sum(black_pixels) > 0

    def test_edges_present_on_dark_bg(self):
        proc = BorderProcessor()
        out = proc.process(_make_bgr_dark())
        black_pixels = np.all(out == 0, axis=2)
        assert np.sum(black_pixels) > 0


class TestGrayscale:
    def test_bgr_output_is_3channel_grey(self):
        proc = GrayscaleProcessor()
        out = proc.process(_make_bgr_light())
        assert out.ndim == 3 and out.shape[2] == 3
        # All channels equal (grey)
        assert np.array_equal(out[:, :, 0], out[:, :, 1])

    def test_bgra_preserves_alpha(self):
        proc = GrayscaleProcessor()
        out = proc.process(_make_bgra())
        assert out.shape[2] == 4


class TestPipeline:
    def test_pipeline_with_bgr_bytes(self, tmp_path):
        img = _make_bgr_light()
        _, buf = cv2.imencode(".png", img)
        results = run_pipeline(buf.tobytes(), tmp_path)
        assert set(results.keys()) == {"silhouette", "border", "grayscale"}
        for path in results.values():
            assert path.exists() and path.stat().st_size > 0

    def test_pipeline_dark_bg(self, tmp_path):
        img = _make_bgr_dark()
        _, buf = cv2.imencode(".jpg", img)
        results = run_pipeline(buf.tobytes(), tmp_path)
        assert set(results.keys()) == {"silhouette", "border", "grayscale"}

    def test_invalid_bytes_raises(self, tmp_path):
        with pytest.raises(ValueError, match="could not decode"):
            run_pipeline(b"not an image", tmp_path)
