"""Operation Registry for SlicerFlow Copilot.

Enforces the core rule:
AI understands. Rules validate. 3D Slicer executes. Verification checks. Humans approve.

Only operations explicitly registered in this whitelist may be executed.
Arbitrary or diagnostic instructions are strictly intercepted and rejected.
"""

from typing import Dict, List, Any, Optional

# The fixed whitelist of supported operations
SUPPORTED_OPERATIONS: Dict[str, Dict[str, Any]] = {
    "inspect_case": {
        "name": "inspect_case",
        "display_name": "Case Inspection",
        "description": "Inspect medical imaging file, verify integrity, extract dimensions and spacing metadata.",
        "requires": [],
        "produces": ["case_metadata"],
    },
    "load_volume": {
        "name": "load_volume",
        "display_name": "Volume Loading",
        "description": "Load 3D medical volume into voxel memory / 3D Slicer MRML scene.",
        "requires": ["inspect_case"],
        "produces": ["volume_node"],
    },
    "select_series": {
        "name": "select_series",
        "display_name": "Series Selection",
        "description": "Select specific series from multi-series DICOM dataset or multi-volume study.",
        "requires": ["inspect_case"],
        "produces": ["series_uid"],
    },
    "preprocess": {
        "name": "preprocess",
        "display_name": "Image Preprocessing",
        "description": "Apply intensity windowing (HU scaling), orientation alignment, or noise reduction.",
        "requires": ["load_volume"],
        "produces": ["preprocessed_volume"],
    },
    "segment": {
        "name": "segment",
        "display_name": "Anatomy Segmentation",
        "description": "Create segmentation labelmap (bone thresholding, airway mask, or verified demo anatomy).",
        "requires": ["load_volume"],
        "produces": ["segmentation_mask"],
    },
    "generate_model": {
        "name": "generate_model",
        "display_name": "3D Model Generation",
        "description": "Convert segmentation labelmap into a 3D closed polygonal surface mesh (STL/OBJ).",
        "requires": ["segment"],
        "produces": ["model_3d"],
    },
    "validate": {
        "name": "validate",
        "display_name": "Output Technical Verification",
        "description": "Run technical integrity tests on volume, segmentation geometry, and 3D surface mesh.",
        "requires": ["load_volume"],
        "produces": ["validation_report"],
    },
    "export": {
        "name": "export",
        "display_name": "Results Export & Packaging",
        "description": "Save 3D meshes, generate JSON reproducibility manifest, and case processing report.",
        "requires": ["load_volume"],
        "produces": ["export_manifest", "case_report"],
    }
}


def is_supported_operation(operation: str) -> bool:
    """Return True if operation is in the fixed registry."""
    return operation in SUPPORTED_OPERATIONS


def get_supported_operations() -> List[str]:
    """Return list of supported operation identifiers."""
    return list(SUPPORTED_OPERATIONS.keys())


def get_operation_details(operation: str) -> Optional[Dict[str, Any]]:
    """Return metadata dict for an operation, or None if unsupported."""
    return SUPPORTED_OPERATIONS.get(operation)


def get_unsupported_operation_message(query: str) -> str:
    """Return structured, compliant message explaining why a request is unsupported."""
    return (
        "UNSUPPORTED REQUEST\n\n"
        "This operation is not supported by the current workflow.\n\n"
        "SlicerFlow Copilot is an imaging workflow automation prototype and does NOT "
        "provide clinical diagnosis, prognostic predictions, or arbitrary code execution.\n\n"
        "Supported actions include:\n"
        "• Inspect case (metadata & integrity)\n"
        "• Load image (NIfTI, NRRD, DICOM)\n"
        "• Prepare / preprocess image\n"
        "• Run supported segmentation (bone, airway, demo anatomy)\n"
        "• Generate 3D model (mesh reconstruction)\n"
        "• Validate output (technical verification)\n"
        "• Export output (STL, manifest, case report)"
    )
