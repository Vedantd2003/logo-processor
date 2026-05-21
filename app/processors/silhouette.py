import cv2
import numpy as np
from .base import ImageProcessor


def _extract_foreground_mask(image: np.ndarray) -> np.ndarray:
    """Return a binary mask of foreground pixels, handling dark and light backgrounds."""
    channels = image.shape[2] if image.ndim == 3 else 1
    h, w = image.shape[:2]

    if channels == 4:
        alpha = image[:, :, 3]
        return (alpha > 10).astype(np.uint8) * 255

    if channels == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Sample corner + edge pixels to estimate background brightness
    border_pixels = np.concatenate([
        gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]
    ])
    bg_brightness = float(np.median(border_pixels))
    bg_is_dark = bg_brightness < 80

    if bg_is_dark and channels == 3:
        # Use HSV value + saturation to find non-background pixels
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        v = hsv[:, :, 2]
        s = hsv[:, :, 1]
        # Pixels that are bright OR colorful are foreground
        mask = np.zeros((h, w), dtype=np.uint8)
        mask[(v.astype(int) > 45) | (s.astype(int) > 35)] = 255
    else:
        # Light background: Otsu threshold
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        # Invert if more than half the image is "foreground" (background got detected)
        if np.sum(mask > 0) > 0.5 * mask.size:
            mask = cv2.bitwise_not(mask)

    return mask


class SilhouetteProcessor(ImageProcessor):
    output_filename = "silhouette.png"

    def process(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]

        mask = _extract_foreground_mask(image)

        # Morphological closing to fill internal gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
        mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=1)

        # Find external contours and draw solid fill
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # White background, black silhouette — clearly visible on any display
        canvas = np.ones((h, w, 3), dtype=np.uint8) * 255
        cv2.drawContours(canvas, contours, -1, (0, 0, 0), thickness=cv2.FILLED)

        return canvas
