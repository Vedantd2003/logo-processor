import cv2
import numpy as np
from .base import ImageProcessor


class GrayscaleProcessor(ImageProcessor):
    output_filename = "grayscale.png"

    def process(self, image: np.ndarray) -> np.ndarray:
        channels = image.shape[2] if image.ndim == 3 else 1

        if channels == 4:
            bgr = image[:, :, :3]
            alpha = image[:, :, 3]
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            return np.dstack([gray_bgr, alpha])
        elif channels == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            # Return as BGR so cv2.imwrite saves it correctly
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        else:
            return image
