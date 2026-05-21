"""Smoke tests for CV processors — verify output shape and dtype."""
import numpy as np
import pytest
import cv2
from pathlib import Path

from app.processors.silhouette import SilhouetteProcessor
from app.processors.border import BorderProcessor
from app.processors.grayscale import GrayscaleProcessor
from app.processors.pipeline import run_pipeline


FIXTURES = Path(__file__).parent / "fixtures"


def _make_bgr(h=64, w=64) -> np.ndarray:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.circle(img, (32, 32), 20, (50, 50, 50), -1)  # dark circle on black bg
    return img


def _make_bgra(h=64, w=64) -> np.ndarray:
    img = np.zeros((h, w, 4), dtype=np.uint8)
    cv2.circle(img, (32, 32), 20, (50, 50, 50, 255), -1)
    return img


class TestSilhouette:
    def test_bgr_output_is_4channel(self):
        proc = SilhouetteProcessor()
        out = proc.process(_make_bgr())
        assert out.ndim == 3 and out.shape[2] == 4

    def test_bgra_output_is_4channel(self):
        proc = SilhouetteProcessor()
        out = proc.process(_make_bgra())
        assert out.ndim == 3 and out.shape[2] == 4

    def test_output_dtype_uint8(self):
        proc = SilhouetteProcessor()
        out = proc.process(_make_bgr())
        assert out.dtype == np.uint8


class TestBorder:
    def test_output_is_4channel(self):
        proc = BorderProcessor()
        out = proc.process(_make_bgr())
        assert out.ndim == 3 and out.shape[2] == 4

    def test_edges_present_in_output(self):
        proc = BorderProcessor()
        out = proc.process(_make_bgr())
        # Some pixels should be non-zero (edges found)
        assert np.any(out[:, :, 3] > 0)


class TestGrayscale:
    def test_bgr_becomes_single_channel(self):
        proc = GrayscaleProcessor()
        out = proc.process(_make_bgr())
        assert out.ndim == 2 or (out.ndim == 3 and out.shape[2] == 1)

    def test_bgra_preserves_alpha(self):
        proc = GrayscaleProcessor()
        out = proc.process(_make_bgra())
        assert out.shape[2] == 4


class TestPipeline:
    def test_pipeline_with_bgr_bytes(self, tmp_path):
        img = _make_bgr()
        _, buf = cv2.imencode(".png", img)
        results = run_pipeline(buf.tobytes(), tmp_path)
        assert set(results.keys()) == {"silhouette", "border", "grayscale"}
        for path in results.values():
            assert path.exists() and path.stat().st_size > 0

    def test_invalid_bytes_raises(self, tmp_path):
        with pytest.raises(ValueError, match="could not decode"):
            run_pipeline(b"not an image", tmp_path)
