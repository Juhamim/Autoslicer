"""Input file validator for technical correctness."""

import os
from typing import Tuple, Optional


class InputValidator:
    """Verifies physical file presence, size, and readable extension."""

    SUPPORTED_EXTENSIONS = [".nii", ".nii.gz", ".nrrd", ".nhdr", ".dcm", ".ima"]

    @classmethod
    def validate(cls, file_path: str) -> Tuple[bool, str]:
        if not file_path:
            return False, "No file path provided."

        if not os.path.exists(file_path):
            return False, f"File does not exist: {file_path}"

        if os.path.isfile(file_path):
            size_bytes = os.path.getsize(file_path)
            if size_bytes == 0:
                return False, f"File is empty (0 bytes): {file_path}"

            name_lower = file_path.lower()
            if not any(name_lower.endswith(ext) for ext in cls.SUPPORTED_EXTENSIONS):
                return False, f"Unsupported file extension: {os.path.basename(file_path)}"

        elif os.path.isdir(file_path):
            # Check for DICOM directory
            files = [f for f in os.listdir(file_path) if not f.startswith(".")]
            if not files:
                return False, f"Directory is empty: {file_path}"

        return True, "Input file is valid and readable."
