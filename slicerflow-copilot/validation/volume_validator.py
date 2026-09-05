"""Volume validator for 3D medical imaging arrays."""
from typing import Tuple
import numpy as np


class VolumeValidator:
    @classmethod
    def validate(cls, arr: np.ndarray) -> Tuple[bool, str]:
        if arr is None:
            return False, "Volume array is None."
        if arr.size == 0:
            return False, "Volume array is empty."
        if not np.isfinite(arr).all():
            return False, "Volume array contains non-finite values (NaN or Inf)."
        if arr.std() == 0:
            return False, "Volume array has zero variance (all identical values)."
        return True, "Volume array is valid."
