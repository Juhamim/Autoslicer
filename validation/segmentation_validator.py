"""Segmentation validator for medical image segmentation masks."""
from typing import Tuple
import numpy as np


class SegmentationValidator:
    @classmethod
    def validate(cls, mask: np.ndarray, arr: np.ndarray) -> Tuple[bool, str]:
        if mask is None:
            return False, "Segmentation mask is None."
        if mask.size == 0:
            return False, "Segmentation mask is empty."
        if np.sum(mask) == 0:
            return False, "Segmentation mask has no segmented voxels."
        if mask.shape != arr.shape:
            return False, f"Segmentation mask shape {mask.shape} does not match volume shape {arr.shape}."
        if not np.isfinite(mask).all():
            return False, "Segmentation mask contains non-finite values."
        return True, "Segmentation mask is valid."
