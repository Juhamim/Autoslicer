"""Natural Language Rule-Based Parser for SlicerFlow Copilot.

Maps natural language requests into structured operations from the supported registry.
Strictly rejects clinical diagnoses and unsupported requests.
"""

import re
from typing import List, Dict, Any, Optional

from core.operation_registry import (
    is_supported_operation,
    get_unsupported_operation_message,
    SUPPORTED_OPERATIONS,
)
from .schemas import ParsedWorkflowIntent

# Keywords indicating clinical diagnosis / medical decision making (STRICTLY FORBIDDEN)
UNSUPPORTED_DIAGNOSTIC_KEYWORDS = [
    "diagnose", "diagnosis", "cancer", "tumor", "tumour", "malignant", "benign",
    "fracture", "lesion", "pneumonia", "nodule", "disease", "pathology", "prescribe",
    "treatment", "curable", "survival", "metastasis", "clinical judgment", "biopsy"
]

# Supported operation triggers
OPERATION_KEYWORDS = {
    "inspect_case": ["inspect", "metadata", "header", "dimensions", "spacing", "check case", "analyze"],
    "load_volume": ["load", "open", "read", "import", "bring in"],
    "select_series": ["series", "select series", "dicom series"],
    "preprocess": ["prepare", "preprocess", "resample", "window", "filter", "normalize", "smooth"],
    "segment": ["segment", "segmentation", "label", "mask", "contour", "isolate"],
    "generate_model": ["generate model", "3d model", "model", "surface", "mesh", "reconstruct", "stl", "obj", "3d"],
    "validate": ["validate", "validation", "verify", "verification", "check output", "integrity"],
    "export": ["export", "save", "download", "package", "output", "manifest", "report"],
}


class RuleBasedParser:
    """Deterministic parser converting user queries into structured workflow intents."""

    @classmethod
    def parse(cls, query: str, context: Optional[Dict[str, Any]] = None) -> ParsedWorkflowIntent:
        text = query.strip().lower()

        # 1. Check for clinical diagnostic requests
        for bad_kw in UNSUPPORTED_DIAGNOSTIC_KEYWORDS:
            pattern = rf"\b{re.escape(bad_kw)}\b"
            if re.search(pattern, text):
                return ParsedWorkflowIntent(
                    intent="unsupported_clinical_request",
                    operations=[],
                    is_supported=False,
                    confidence=1.0,
                    explanation="Medical diagnosis / clinical decision requests are outside the system scope.",
                    unsupported_reason=get_unsupported_operation_message(query)
                )

        # 2. Extract anatomical target if specified
        target_anatomy = "bone"
        lower_threshold = 200.0  # HU — calibrated clinical bone window
        upper_threshold = 2000.0  # HU

        if any(w in text for w in ["airway", "lung", "air", "trachea"]):
            target_anatomy = "airway"
            lower_threshold = -950.0
            upper_threshold = -400.0
        elif any(w in text for w in ["soft tissue", "muscle", "organ"]):
            target_anatomy = "soft_tissue"
            lower_threshold = -50.0
            upper_threshold = 150.0
        elif any(w in text for w in ["fat", "adipose", "subcutaneous"]):
            target_anatomy = "fat"
            lower_threshold = -120.0
            upper_threshold = -50.0
        elif any(w in text for w in ["bone", "spine", "vertebra", "rib", "skull", "skeleton"]):
            target_anatomy = "bone"
            lower_threshold = 200.0
            upper_threshold = 2000.0

        # 3. Detect high-level intents
        # Scenario A: "Prepare this CT scan and generate a 3D model" / "Prepare case"
        is_prepare = any(w in text for w in ["prepare", "prep", "case preparation", "process scan"])
        is_model = any(w in text for w in ["3d model", "model", "mesh", "3d", "reconstruct"])
        is_segment = any(w in text for w in ["segment", "segmentation", "mask", "contour"])
        is_inspect_only = (
            any(w in text for w in ["inspect", "metadata", "dimensions", "info"])
            and not (is_prepare or is_model or is_segment)
        )

        operations: List[str] = []

        if is_inspect_only:
            intent = "inspect_case"
            operations = ["inspect_case"]
            explanation = "User requested case inspection and metadata extraction."

        elif is_prepare and is_model:
            # Full end-to-end standard workflow
            intent = "prepare_and_model"
            operations = [
                "inspect_case",
                "load_volume",
                "preprocess",
                "segment",
                "generate_model",
                "validate",
                "export"
            ]
            explanation = "Prepared case, segmented anatomy, generated 3D surface model, verified and exported."

        elif is_model or is_segment:
            intent = "segment_and_model" if is_model else "segment_case"
            operations = [
                "inspect_case",
                "load_volume",
                "segment",
            ]
            if is_model:
                operations.append("generate_model")
            operations.extend(["validate", "export"])
            explanation = f"Segment {target_anatomy} and generate verified outputs."

        elif is_prepare:
            intent = "prepare_case"
            operations = [
                "inspect_case",
                "load_volume",
                "preprocess",
                "validate",
                "export"
            ]
            explanation = "Inspect, load, preprocess, validate, and export case."

        else:
            # Fallback: Match individual operations mentioned in query
            detected = []
            for op, kws in OPERATION_KEYWORDS.items():
                if any(re.search(rf"\b{re.escape(k)}\b", text) for k in kws):
                    detected.append(op)

            if detected:
                # Always ensure inspect_case and load_volume precede downstream operations
                ordered_ops = []
                for std_op in ["inspect_case", "load_volume", "select_series", "preprocess", "segment", "generate_model", "validate", "export"]:
                    if std_op in detected or (std_op == "inspect_case" and len(detected) > 0):
                        if std_op not in ordered_ops:
                            ordered_ops.append(std_op)
                operations = ordered_ops
                intent = "custom_workflow"
                explanation = f"Matched {len(operations)} operations from query."
            else:
                # Default canonical workflow
                intent = "default_case_preparation"
                operations = [
                    "inspect_case",
                    "load_volume",
                    "preprocess",
                    "segment",
                    "generate_model",
                    "validate",
                    "export"
                ]
                explanation = "Executed standard automated preparation and 3D reconstruction pipeline."

        # Filter against whitelist strictly
        validated_ops = [op for op in operations if is_supported_operation(op)]

        return ParsedWorkflowIntent(
            intent=intent,
            operations=validated_ops,
            parameters={
                "target_anatomy": target_anatomy,
                "lower_threshold": lower_threshold,
                "upper_threshold": upper_threshold,
                "export_format": "stl",
            },
            confidence=0.95,
            explanation=explanation,
            is_supported=True
        )
