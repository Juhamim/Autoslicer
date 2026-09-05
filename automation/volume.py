"""Volume loading, windowing, and orthogonal slice extraction."""

import numpy as np
import SimpleITK as sitk
from typing import Tuple, Dict, Any, Optional


class VolumeProcessor:
    """Manages voxel data loading, CT windowing, and orthogonal slice extraction."""

    # Standard CT window presets [Window Width (W), Window Level (L)]
    WINDOW_PRESETS = {
        "bone": (1500, 300),
        "soft_tissue": (350, 40),
        "lung": (1500, -600),
        "brain": (80, 40),
        "default": (1000, 0)
    }

    @classmethod
    def load_volume(cls, file_path: str) -> Tuple[np.ndarray, Tuple[float, float, float], Tuple[float, float, float]]:
        """Load image and return (array_zyx, spacing_xyz, origin_xyz)."""
        image = sitk.ReadImage(file_path)
        arr = sitk.GetArrayFromImage(image)  # Shape (Z, Y, X)
        spacing = image.GetSpacing()  # (Sx, Sy, Sz)
        origin = image.GetOrigin()  # (Ox, Oy, Oz)
        return arr, spacing, origin

    @classmethod
    def apply_windowing(cls, arr: np.ndarray, preset: str = "bone") -> np.ndarray:
        """Apply CT window/level linear normalization to [0, 255] uint8."""
        width, level = cls.WINDOW_PRESETS.get(preset.lower(), cls.WINDOW_PRESETS["default"])
        min_val = level - (width / 2.0)
        max_val = level + (width / 2.0)

        clipped = np.clip(arr, min_val, max_val)
        normalized = ((clipped - min_val) / (max_val - min_val) * 255.0).astype(np.uint8)
        return normalized

    @classmethod
    def get_orthogonal_slices(
        cls,
        arr: np.ndarray,
        axial_idx: Optional[int] = None,
        coronal_idx: Optional[int] = None,
        sagittal_idx: Optional[int] = None,
        preset: str = "soft_tissue"
    ) -> Dict[str, np.ndarray]:
        """Extract axial (Z), coronal (Y), and sagittal (X) 2D slice images normalized to uint8."""
        nz, ny, nx = arr.shape
        az = axial_idx if axial_idx is not None else nz // 2
        cy = coronal_idx if coronal_idx is not None else ny // 2
        sx = sagittal_idx if sagittal_idx is not None else nx // 2

        az = int(np.clip(az, 0, nz - 1))
        cy = int(np.clip(cy, 0, ny - 1))
        sx = int(np.clip(sx, 0, nx - 1))

        # Windows
        axial_slice = cls.apply_windowing(arr[az, :, :], preset)
        coronal_slice = cls.apply_windowing(arr[:, cy, :], preset)
        sagittal_slice = cls.apply_windowing(arr[:, :, sx], preset)

        return {
            "axial": axial_slice,
            "coronal": coronal_slice,
            "sagittal": sagittal_slice,
            "indices": {"axial": az, "coronal": cy, "sagittal": sx},
            "shape": (nz, ny, nx)
        }
