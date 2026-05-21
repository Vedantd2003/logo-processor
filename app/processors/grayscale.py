import cv2
import numpy as np
from .base import ImageProcessor


class GrayscaleProcessor(ImageProcessor):
    output_filename = "grayscale.png"

    def process(self, image: np.ndarray) -> np.ndarray:
        channels = image.shape[2] if image.ndim == 3 else 1

        if channels == 4:
            # Preserve alpha, convert only the BGR portion
            bgr = image[:, :, :3]
            alpha = image[:, :, 3]
            gray_bgr = cv2.cvtColor(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
            output = np.dstack([gray_bgr, alpha])
            return output
        elif channels == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            return gray
        else:
            # Already single-channel
            return image
