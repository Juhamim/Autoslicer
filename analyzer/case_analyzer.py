"""Case Analyzer Engine for medical imaging files.

Inspects medical cases (NIfTI, NRRD, DICOM) and extracts verified metadata.
Does not invent metadata if not present.
"""

import os
from pathlib import Path
from typing import Optional
import numpy as np

from .metadata import CaseMetadata

# Optional imports handled gracefully
try:
    import SimpleITK as sitk
except ImportError:
    sitk = None

try:
    import pydicom
except ImportError:
    pydicom = None

try:
    import nibabel as nib
except ImportError:
    nib = None


class CaseAnalyzer:
    """Inspects medical image volumes and extracts technical metadata."""

    # 3D mesh/model file extensions
    MODEL_EXTENSIONS = {".vtk", ".stl", ".obj", ".ply", ".vtp", ".vtu", ".g", ".byu", ".off"}

    @staticmethod
    def detect_format(path_str: str) -> str:
        """Detect file format based on path and extension."""
        path = Path(path_str)
        if path.is_dir():
            # Check if directory contains DICOM files
            dcm_files = list(path.glob("*.dcm")) + list(path.glob("*.ima"))
            if dcm_files:
                return "DICOM"
            # Check if directory contains 3D mesh files (e.g. MESHES_VTK)
            for ext in CaseAnalyzer.MODEL_EXTENSIONS:
                mesh_files = list(path.glob("*" + ext))
                if mesh_files:
                    return "VTK_MESH_DIR"
            return "Unknown"

        name_lower = path.name.lower()
        if name_lower.endswith(".nii.gz") or name_lower.endswith(".nii"):
            return "NIfTI"
        elif name_lower.endswith(".nrrd") or name_lower.endswith(".nhdr"):
            return "NRRD"
        elif name_lower.endswith(".dcm") or name_lower.endswith(".ima"):
            return "DICOM"
        elif name_lower.endswith(".mha") or name_lower.endswith(".mhd"):
            return "MetaImage"
        # 3D mesh/model formats
        ext = path.suffix.lower()
        if ext in CaseAnalyzer.MODEL_EXTENSIONS:
            return "3D_MODEL"
        return "Unknown"

    @classmethod
    def analyze_case(cls, file_path: str) -> CaseMetadata:
        """Inspect the case and return a structured CaseMetadata object."""
        if not os.path.exists(file_path):
            return CaseMetadata(
                file_name=os.path.basename(file_path),
                file_path=file_path,
                file_format="Unknown",
                status="INVALID",
                error_message=f"File or directory does not exist: {file_path}"
            )

        file_format = cls.detect_format(file_path)
        file_name = os.path.basename(file_path)

        if file_format == "Unknown":
            return CaseMetadata(
                file_name=file_name,
                file_path=file_path,
                file_format="Unknown",
                status="INVALID",
                error_message=f"Unsupported or unrecognized file format for {file_name}"
            )

        # 3D mesh/model files are not volumetric — return basic metadata
        if file_format in ("3D_MODEL", "VTK_MESH_DIR"):
            return CaseMetadata(
                file_name=file_name,
                file_path=file_path,
                file_format=file_format,
                modality="3D_MESH",
                status="VALID",
            )

        # Process with SimpleITK if available
        if sitk is not None:
            return cls._analyze_with_sitk(file_path, file_format)
        
        # Fallback to nibabel / pydicom if SimpleITK not available
        return cls._analyze_fallback(file_path, file_format)

    @classmethod
    def _analyze_with_sitk(cls, file_path: str, file_format: str) -> CaseMetadata:
        try:
            if file_format == "DICOM" and os.path.isdir(file_path):
                reader = sitk.ImageSeriesReader()
                series_ids = reader.GetGDCMSeriesIDs(file_path)
                series_count = len(series_ids)
                if not series_ids:
                    return CaseMetadata(
                        file_name=os.path.basename(file_path),
                        file_path=file_path,
                        file_format="DICOM",
                        status="INVALID",
                        error_message="No valid DICOM series found in directory."
                    )
                dicom_names = reader.GetGDCMSeriesFileNames(file_path, series_ids[0])
                reader.SetFileNames(dicom_names)
                image = reader.Execute()
            else:
                image = sitk.ReadImage(file_path)
                series_count = 1

            size = image.GetSize()  # (Nx, Ny, Nz)
            spacing = image.GetSpacing()  # (Sx, Sy, Sz)
            origin = image.GetOrigin()  # (Ox, Oy, Oz)

            # Compute intensity bounds using numpy array
            arr = sitk.GetArrayViewFromImage(image)
            val_min = float(np.min(arr))
            val_max = float(np.max(arr))
            val_mean = float(np.mean(arr))

            # Extract DICOM tags if present
            patient_id = None
            study_desc = None
            series_desc = None
            modality = "Unknown"

            for key in image.GetMetaDataKeys():
                k_low = key.lower()
                if "modality" in k_low:
                    modality = image.GetMetaData(key).strip().upper()
                elif "patientid" in k_low or "0010|0020" in k_low:
                    patient_id = image.GetMetaData(key).strip()
                elif "studydescription" in k_low or "0008|1030" in k_low:
                    study_desc = image.GetMetaData(key).strip()
                elif "seriesdescription" in k_low or "0008|103e" in k_low:
                    series_desc = image.GetMetaData(key).strip()

            # Direct pydicom inspection if DICOM file/folder
            if pydicom is not None and file_format == "DICOM":
                try:
                    dcm_sample_path = file_path
                    if os.path.isdir(file_path):
                        for f in os.listdir(file_path):
                            if f.lower().endswith((".dcm", ".ima")) or not "." in f:
                                dcm_sample_path = os.path.join(file_path, f)
                                break
                    if os.path.isfile(dcm_sample_path):
                        ds = pydicom.dcmread(dcm_sample_path, stop_before_pixels=True)
                        patient_id = patient_id or getattr(ds, "PatientID", None)
                        study_desc = study_desc or getattr(ds, "StudyDescription", None)
                        series_desc = series_desc or getattr(ds, "SeriesDescription", None)
                        modality = getattr(ds, "Modality", modality)
                except Exception:
                    pass

            if modality == "Unknown":
                # CT volumes typically feature Hounsfield units ranging from -1024 to 1000+
                if val_min <= -500 and val_max >= 500:
                    modality = "CT"
                elif val_min >= 0 and val_max > 50:
                    modality = "MR"

            return CaseMetadata(
                file_name=os.path.basename(file_path),
                file_path=file_path,
                file_format=file_format,
                modality=modality,
                patient_id=patient_id,
                study_description=study_desc,
                series_description=series_desc,
                dimensions=tuple(size),
                spacing=tuple(spacing),
                origin=tuple(origin),
                intensity_min=val_min,
                intensity_max=val_max,
                intensity_mean=val_mean,
                series_count=series_count,
                status="VALID"
            )
        except Exception as exc:
            return CaseMetadata(
                file_name=os.path.basename(file_path),
                file_path=file_path,
                file_format=file_format,
                status="INVALID",
                error_message=f"Failed to read image volume: {str(exc)}"
            )

    @classmethod
    def _analyze_fallback(cls, file_path: str, file_format: str) -> CaseMetadata:
        """Fallback using nibabel for NIfTI or pydicom for DICOM."""
        try:
            if file_format == "NIfTI" and nib is not None:
                img = nib.load(file_path)
                shape = img.shape[:3]
                zooms = img.header.get_zooms()[:3]
                data = img.get_fdata()
                return CaseMetadata(
                    file_name=os.path.basename(file_path),
                    file_path=file_path,
                    file_format="NIfTI",
                    modality="CT" if data.min() <= -500 else "Unknown",
                    dimensions=(int(shape[0]), int(shape[1]), int(shape[2])),
                    spacing=(float(zooms[0]), float(zooms[1]), float(zooms[2])),
                    intensity_min=float(np.min(data)),
                    intensity_max=float(np.max(data)),
                    intensity_mean=float(np.mean(data)),
                    status="VALID"
                )
            elif file_format == "DICOM" and pydicom is not None and os.path.isfile(file_path):
                ds = pydicom.dcmread(file_path)
                modality = getattr(ds, "Modality", "Unknown")
                rows = getattr(ds, "Rows", 512)
                cols = getattr(ds, "Columns", 512)
                spc = getattr(ds, "PixelSpacing", [1.0, 1.0])
                slice_thick = getattr(ds, "SliceThickness", 1.0)
                return CaseMetadata(
                    file_name=os.path.basename(file_path),
                    file_path=file_path,
                    file_format="DICOM",
                    modality=modality,
                    dimensions=(int(cols), int(rows), 1),
                    spacing=(float(spc[0]), float(spc[1]), float(slice_thick)),
                    status="VALID"
                )
        except Exception as e:
            return CaseMetadata(
                file_name=os.path.basename(file_path),
                file_path=file_path,
                file_format=file_format,
                status="INVALID",
                error_message=f"Fallback parser error: {str(e)}"
            )

        return CaseMetadata(
            file_name=os.path.basename(file_path),
            file_path=file_path,
            file_format=file_format,
            status="WARNING",
            error_message="Partial metadata: Image libraries unavailable for deep inspection."
        )
