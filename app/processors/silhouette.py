import cv2
import numpy as np
from .base import ImageProcessor


def _auto_invert_if_needed(binary: np.ndarray) -> np.ndarray:
    """Flip binary mask if foreground covers more than 50% — logos are rarely full-frame."""
    foreground_ratio = np.sum(binary > 0) / binary.size
    if foreground_ratio > 0.5:
        return cv2.bitwise_not(binary)
    return binary


class SilhouetteProcessor(ImageProcessor):
    output_filename = "silhouette.png"

    def process(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        channels = image.shape[2] if image.ndim == 3 else 1

        if channels == 4:
            # Use alpha channel as mask directly
            alpha = image[:, :, 3]
            mask = (alpha > 10).astype(np.uint8) * 255
        else:
            # Convert to grayscale and threshold
            if channels == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image

            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            _, binary = cv2.threshold(
                blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )
            mask = _auto_invert_if_needed(binary)

        # Morphological closing to fill internal holes
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        # Find external contours and draw filled shapes
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        canvas = np.zeros((h, w, 4), dtype=np.uint8)
        cv2.drawContours(canvas, contours, -1, (0, 0, 0, 255), thickness=cv2.FILLED)

        return canvas
