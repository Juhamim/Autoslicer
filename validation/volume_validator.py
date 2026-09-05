"""Volume technical validator."""

from typing import Tuple, Any
import numpy as np


class VolumeValidator:
    """Verifies loaded volume voxel statistics and non-degeneracy."""

    @classmethod
    def validate(cls, volume_data: Any) -> Tuple[bool, str]:
        if volume_data is None:
            return False, "Volume data is None."

        # Support SimpleITK Image or numpy ndarray
        if hasattr(volume_data, "GetSize"):
            size = volume_data.GetSize()
            if any(dim <= 0 for dim in size):
                return False, f"Invalid volume dimensions: {size}"
            return True, f"Volume validated with dimensions {size}."

        if isinstance(volume_data, np.ndarray):
            if volume_data.ndim != 3:
                return False, f"Expected 3D volume, got {volume_data.ndim}D array."
            if volume_data.size == 0:
                return False, "Volume array is empty."
            if not np.all(np.isfinite(volume_data)):
                return False, "Volume contains NaN or infinite values."
            std_val = float(np.std(volume_data))
            if std_val == 0.0:
                return False, "Volume has zero intensity variance (flat uniform array)."

            return True, f"Volume validated: shape={volume_data.shape}, std={std_val:.2f}."

        return False, f"Unrecognized volume data type: {type(volume_data)}"
