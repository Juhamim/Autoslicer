"""Output deliverables technical validator."""

import os
import json
from typing import Tuple, Dict, Any


class OutputValidator:
    """Verifies that generated 3D models and manifest files are physically valid."""

    @classmethod
    def validate_mesh(cls, vertices_count: int, faces_count: int) -> Tuple[bool, str]:
        if vertices_count < 4 or faces_count < 4:
            return False, f"Degenerate 3D surface mesh: {vertices_count} vertices, {faces_count} faces."
        return True, f"Valid 3D surface mesh: {vertices_count} vertices, {faces_count} triangular faces."

    @classmethod
    def validate_export_file(cls, file_path: str) -> Tuple[bool, str]:
        if not os.path.exists(file_path):
            return False, f"Export file was not created: {file_path}"
        if os.path.getsize(file_path) == 0:
            return False, f"Export file is 0 bytes: {file_path}"
        return True, f"Export file verified: {os.path.basename(file_path)} ({os.path.getsize(file_path)} bytes)"

    @classmethod
    def validate_manifest(cls, manifest_path: str) -> Tuple[bool, str]:
        if not os.path.exists(manifest_path):
            return False, f"Manifest file not found: {manifest_path}"
        try:
            with open(manifest_path, "r") as f:
                data = json.load(f)
            required_keys = ["project", "case_id", "workflow", "steps", "final_status"]
            missing = [k for k in required_keys if k not in data]
            if missing:
                return False, f"Manifest missing required keys: {', '.join(missing)}"
            return True, f"Manifest JSON structure verified ({len(data['steps'])} steps recorded)."
        except Exception as e:
            return False, f"Invalid manifest JSON: {str(e)}"
