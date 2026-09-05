"""Output validator for 3D mesh and export verification."""
from typing import Tuple
import os
import json
import hashlib


class OutputValidator:
    @classmethod
    def validate_mesh(cls, vertices_count: int, faces_count: int) -> Tuple[bool, str]:
        if vertices_count <= 0:
            return False, "Mesh has no vertices."
        if faces_count <= 0:
            return False, "Mesh has no faces."
        if vertices_count < 3:
            return False, "Mesh has fewer than 3 vertices."
        return True, "3D mesh is valid."

    @classmethod
    def validate_export_file(cls, file_path: str) -> Tuple[bool, str]:
        if not os.path.exists(file_path):
            return False, f"Export file does not exist: {file_path}"
        if os.path.getsize(file_path) == 0:
            return False, f"Export file is empty: {file_path}"
        return True, f"Export file verified: {file_path}"

    @classmethod
    def validate_manifest(cls, manifest_path: str) -> Tuple[bool, str]:
        if not os.path.exists(manifest_path):
            return False, f"Manifest file does not exist: {manifest_path}"
        if os.path.getsize(manifest_path) == 0:
            return False, f"Manifest file is empty: {manifest_path}"
        try:
            with open(manifest_path, "r") as f:
                data = json.load(f)
            required_keys = ["project", "case_id", "plan_id", "timestamp", "input", "workflow", "outputs"]
            for key in required_keys:
                if key not in data:
                    return False, f"Manifest missing required key: {key}"
            if "sha256" not in data.get("input", {}):
                return False, "Manifest input missing sha256 hash."
            return True, "Manifest is valid and complete."
        except (json.JSONDecodeError, IOError) as exc:
            return False, f"Manifest parsing failed: {str(exc)}"

    @classmethod
    def compute_sha256(cls, file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
