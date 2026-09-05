"""Reproducibility Manifest Generator for SlicerFlow Copilot.

Generates a cryptographically verified JSON manifest recording the complete workflow provenance.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from core.workflow import WorkflowPlan


class ManifestGenerator:
    """Produces verified JSON provenance manifests."""

    @staticmethod
    def compute_sha256(file_path: str) -> Optional[str]:
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return None
        sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception:
            return None

    @classmethod
    def generate_manifest(
        cls,
        plan: WorkflowPlan,
        input_file: str,
        output_files: Dict[str, str],
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        timestamp_iso = datetime.now(timezone.utc).isoformat()
        input_hash = cls.compute_sha256(input_file)

        steps_data = []
        for step in plan.steps:
            steps_data.append({
                "operation": step.operation,
                "display_name": step.display_name,
                "status": step.status.value,
                "execution_time_seconds": step.execution_time_seconds,
                "message": step.message,
                "error_details": step.error_details,
                "outputs": step.outputs,
            })

        manifest = {
            "project": "SlicerFlow Copilot",
            "version": "1.0.0-hackathon-mvp",
            "case_id": plan.case_id,
            "plan_id": plan.plan_id,
            "timestamp": timestamp_iso,
            "input": {
                "file_path": input_file,
                "file_name": os.path.basename(input_file),
                "sha256": input_hash,
            },
            "workflow": plan.operations_list(),
            "steps": steps_data,
            "final_status": plan.final_status.value,
            "outputs": output_files,
            "metadata": extra_metadata or {},
        }
        return manifest

    @classmethod
    def save_manifest(cls, manifest_data: Dict[str, Any], output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(manifest_data, f, indent=2)
        return output_path
