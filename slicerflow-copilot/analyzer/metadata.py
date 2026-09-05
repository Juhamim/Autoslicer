"""Metadata representation for medical imaging cases."""

from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, Any


@dataclass
class CaseMetadata:
    file_name: str
    file_path: str
    file_format: str  # 'NIfTI', 'NRRD', 'DICOM', 'Unknown'
    modality: str = "Unknown"  # 'CT', 'MR', 'PET', 'Unknown'
    patient_id: Optional[str] = None
    study_description: Optional[str] = None
    series_description: Optional[str] = None
    dimensions: Optional[Tuple[int, int, int]] = None  # (Nx, Ny, Nz)
    spacing: Optional[Tuple[float, float, float]] = None  # (Sx, Sy, Sz) in mm
    origin: Optional[Tuple[float, float, float]] = None  # (Ox, Oy, Oz) in mm
    intensity_min: Optional[float] = None
    intensity_max: Optional[float] = None
    intensity_mean: Optional[float] = None
    series_count: int = 1
    status: str = "VALID"  # 'VALID', 'INVALID', 'WARNING'
    error_message: Optional[str] = None
    extra_attributes: Dict[str, Any] = field(default_factory=dict)

    def summary_text(self) -> str:
        dim_str = f"{self.dimensions[0]} × {self.dimensions[1]} × {self.dimensions[2]}" if self.dimensions else "Unavailable"
        spc_str = f"{self.spacing[0]:.2f} × {self.spacing[1]:.2f} × {self.spacing[2]:.2f} mm" if self.spacing else "Unavailable"
        hu_str = f"[{self.intensity_min:.1f}, {self.intensity_max:.1f}]" if self.intensity_min is not None and self.intensity_max is not None else "Unavailable"
        pt_info = f"\nPatient ID: {self.patient_id}" if self.patient_id else ""
        study_info = f"\nStudy: {self.study_description}" if self.study_description else ""

        return (
            f"File: {self.file_name}\n"
            f"Format: {self.file_format}\n"
            f"Modality: {self.modality}{pt_info}{study_info}\n"
            f"Dimensions: {dim_str}\n"
            f"Spacing: {spc_str}\n"
            f"Intensity Bounds: {hu_str}\n"
            f"Series Count: {self.series_count}\n"
            f"Status: {self.status}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_name": self.file_name,
            "file_path": self.file_path,
            "file_format": self.file_format,
            "modality": self.modality,
            "patient_id": self.patient_id,
            "study_description": self.study_description,
            "series_description": self.series_description,
            "dimensions": list(self.dimensions) if self.dimensions else None,
            "spacing": [round(s, 4) for s in self.spacing] if self.spacing else None,
            "origin": [round(o, 4) for o in self.origin] if self.origin else None,
            "intensity_min": round(self.intensity_min, 2) if self.intensity_min is not None else None,
            "intensity_max": round(self.intensity_max, 2) if self.intensity_max is not None else None,
            "intensity_mean": round(self.intensity_mean, 2) if self.intensity_mean is not None else None,
            "series_count": self.series_count,
            "status": self.status,
            "error_message": self.error_message,
        }
