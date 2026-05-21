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
            gray = image.copy()

        # Slight blur to reduce noise before edge detection
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Auto-compute Canny thresholds from the image median
        median = float(np.median(blurred))
        lower = int(max(0, 0.5 * median))
        upper = int(min(255, 1.5 * median))

        # Ensure reasonable thresholds even for very dark or uniform images
        if upper - lower < 20:
            lower, upper = 30, 100

        edges = cv2.Canny(blurred, lower, upper)

        # Dilate to thicken lines so they're visible at any size
        kernel = np.ones((2, 2), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=2)

        # White background, black edge lines — visible on any display
        canvas = np.ones((h, w, 3), dtype=np.uint8) * 255
        canvas[edges > 0] = [0, 0, 0]

        return canvas
