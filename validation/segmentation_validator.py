"""Segmentation technical validator."""

from typing import Tuple, Any
import numpy as np


class SegmentationValidator:
    """Verifies segmentation mask non-emptiness and spatial compatibility."""

    @classmethod
    def validate(cls, mask_data: Any, reference_volume: Any = None) -> Tuple[bool, str]:
        if mask_data is None:
            return False, "Segmentation mask is None."

        if hasattr(mask_data, "GetSize"):
            size = mask_data.GetSize()
            if reference_volume and hasattr(reference_volume, "GetSize"):
                if size != reference_volume.GetSize():
                    return False, f"Segmentation dimension mismatch: mask {size} vs volume {reference_volume.GetSize()}."
            return True, f"Segmentation verified with dimensions {size}."

        if isinstance(mask_data, np.ndarray):
            if mask_data.size == 0:
                return False, "Segmentation mask is empty."
            voxel_count = int(np.sum(mask_data > 0))
            if voxel_count == 0:
                return False, "Segmentation mask contains 0 segmented voxels (empty mask)."

            if reference_volume is not None and isinstance(reference_volume, np.ndarray):
                if mask_data.shape != reference_volume.shape:
                    return False, f"Mask shape {mask_data.shape} does not match volume shape {reference_volume.shape}."

            total_voxels = mask_data.size
            percentage = (voxel_count / total_voxels) * 100.0
            return True, f"Segmentation verified: {voxel_count} voxels ({percentage:.2f}% of volume)."

        return False, f"Unrecognized segmentation mask type: {type(mask_data)}"
