"""Segmentation Engine for SlicerFlow Copilot.

Provides intensity-threshold and labelmap generation for bone, airway, and anatomy.
"""

import numpy as np
from typing import Tuple, Dict, Any, Optional
from scipy.ndimage import binary_closing, binary_opening


class SegmentationEngine:
    """Performs validated medical image segmentation."""

    SEGMENTATION_PRESETS = {
        "bone": {"lower": 200.0, "upper": 2000.0, "color": "#F4F1EA", "name": "Bone (Cortical & Trabecular)"},
        "airway": {"lower": -950.0, "upper": -400.0, "color": "#5BC0BE", "name": "Airway / Lung Parenchyma"},
        "soft_tissue": {"lower": -50.0, "upper": 150.0, "color": "#E56B6F", "name": "Soft Tissue / Muscle"},
        "fat": {"lower": -120.0, "upper": -50.0, "color": "#FFD166", "name": "Fat / Adipose"},
    }

    @classmethod
    def segment_by_threshold(
        cls,
        arr: np.ndarray,
        lower: float = 250.0,
        upper: float = 2000.0,
        spacing: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        clean_morphology: bool = True
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Apply thresholding to 3D voxel array and return binary mask (0 or 1) and statistics."""
        mask = (arr >= lower) & (arr <= upper)

        if clean_morphology and np.any(mask):
            # 3D morphological cleanup: close small holes and remove single-voxel noise
            mask = binary_closing(mask, structure=np.ones((3, 3, 3)))
            mask = binary_opening(mask, structure=np.ones((2, 2, 2)))

        mask_uint8 = mask.astype(np.uint8)
        segmented_voxels = int(np.sum(mask_uint8))
        total_voxels = mask_uint8.size

        # Voxel spacing: spacing is (Sx, Sy, Sz), volume voxel size is Sx * Sy * Sz in mm^3
        voxel_volume_mm3 = spacing[0] * spacing[1] * spacing[2]
        volume_cm3 = round((segmented_voxels * voxel_volume_mm3) / 1000.0, 3)

        stats = {
            "segmented_voxels": segmented_voxels,
            "total_voxels": total_voxels,
            "percentage": round((segmented_voxels / total_voxels) * 100.0, 2),
            "volume_cm3": volume_cm3,
            "threshold_range": [lower, upper],
            "spacing": spacing
        }

        return mask_uint8, stats
