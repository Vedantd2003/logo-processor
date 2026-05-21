import cv2
import numpy as np
from .base import ImageProcessor


def _extract_foreground_mask(image: np.ndarray) -> np.ndarray:
    channels = image.shape[2] if image.ndim == 3 else 1

    if channels == 4:
        return (image[:, :, 3] > 10).astype(np.uint8) * 255

    if channels == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    border_pixels = np.concatenate([
        gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]
    ])
    bg_is_dark = float(np.median(border_pixels)) < 80

    if bg_is_dark and channels == 3:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        v, s = hsv[:, :, 2], hsv[:, :, 1]
        mask = np.zeros(gray.shape, dtype=np.uint8)
        mask[(v.astype(int) > 45) | (s.astype(int) > 35)] = 255
    else:
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        if np.sum(mask > 0) > 0.5 * mask.size:
            mask = cv2.bitwise_not(mask)

    return mask


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    """Fill any enclosed holes inside the foreground using flood fill from the border."""
    # Invert: foreground=0, background+holes=255
    inv = cv2.bitwise_not(mask)
    # Pad so the flood-fill seed (0,0) is guaranteed to be background
    padded = cv2.copyMakeBorder(inv, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=255)
    # Flood fill background (255) with 0 — unreachable interior holes stay 255
    flood_m = np.zeros((padded.shape[0] + 2, padded.shape[1] + 2), dtype=np.uint8)
    cv2.floodFill(padded, flood_m, (0, 0), 0)
    # Remove padding and merge: original foreground | interior holes
    holes = padded[1:-1, 1:-1]
    return cv2.bitwise_or(mask, holes)


class SilhouetteProcessor(ImageProcessor):
    output_filename = "silhouette.png"

    def process(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]

        # Step 1: rough foreground mask
        mask = _extract_foreground_mask(image)

        # Step 2: morphological closing to bridge nearby regions
        k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_close, iterations=4)

        # Step 3: flood-fill to eliminate all interior holes
        mask = _fill_holes(mask)

        # Step 4: slight dilation so the silhouette fully covers the subject
        k_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.dilate(mask, k_dilate, iterations=1)

        # Step 5: draw the largest external contours as solid fill
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        canvas = np.ones((h, w, 3), dtype=np.uint8) * 255  # white background
        cv2.drawContours(canvas, contours, -1, (0, 0, 0), thickness=cv2.FILLED)

        return canvas
