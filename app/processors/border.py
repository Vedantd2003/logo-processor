import cv2
import numpy as np
from .base import ImageProcessor


class BorderProcessor(ImageProcessor):
    output_filename = "border.png"

    def process(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        channels = image.shape[2] if image.ndim == 3 else 1

        if channels == 4:
            gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
        elif channels == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Auto-compute Canny thresholds from image median
        median = float(np.median(blurred))
        lower = int(max(0, 0.66 * median))
        upper = int(min(255, 1.33 * median))

        # Ensure we get some edges even on very dark/light images
        if upper < 30:
            lower, upper = 10, 50
        elif lower > 200:
            lower, upper = 100, 200

        edges = cv2.Canny(blurred, lower, upper)

        # Slight dilation to make thin lines visible
        dilation_kernel = np.ones((2, 2), np.uint8)
        edges = cv2.dilate(edges, dilation_kernel, iterations=1)

        canvas = np.zeros((h, w, 4), dtype=np.uint8)
        canvas[edges > 0] = [0, 0, 0, 255]

        return canvas
