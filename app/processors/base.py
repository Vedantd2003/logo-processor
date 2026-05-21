from abc import ABC, abstractmethod
from pathlib import Path
import numpy as np
import cv2


class ImageProcessor(ABC):
    output_filename: str

    @abstractmethod
    def process(self, image: np.ndarray) -> np.ndarray:
        """Take input array (BGRA or BGR), return output array."""

    def save(self, output: np.ndarray, out_dir: Path) -> Path:
        path = out_dir / self.output_filename
        cv2.imwrite(str(path), output)
        return path
