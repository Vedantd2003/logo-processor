from pathlib import Path
import numpy as np
import cv2

from .silhouette import SilhouetteProcessor
from .border import BorderProcessor
from .grayscale import GrayscaleProcessor

PROCESSORS = [SilhouetteProcessor(), BorderProcessor(), GrayscaleProcessor()]


def run_pipeline(image_bytes: bytes, out_dir: Path) -> dict[str, Path]:
    """Decode image and run all 3 processors. Returns dict of name -> output path."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)

    if image is None:
        raise ValueError("OpenCV could not decode the uploaded image.")

    results: dict[str, Path] = {}
    for processor in PROCESSORS:
        name = processor.output_filename.split(".")[0]
        try:
            output = processor.process(image)
            path = processor.save(output, out_dir)
            results[name] = path
        except Exception as exc:
            raise RuntimeError(f"Processing failed at stage '{name}': {exc}") from exc

    return results
