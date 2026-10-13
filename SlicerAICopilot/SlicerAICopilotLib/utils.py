"""Utility functions for Slicer AI Copilot."""

import os
import re
from typing import List, Optional
from pathlib import Path


def fuzzy_match(query: str, candidates: List[str]) -> List[str]:
    """Find candidates that match the query with fuzzy matching."""
    query_lower = query.lower().replace(" ", "").replace("_", "").replace("-", "")
    matches = []
    
    for candidate in candidates:
        candidate_lower = candidate.lower().replace(" ", "").replace("_", "").replace("-", "")
        
        if query_lower == candidate_lower:
            matches.insert(0, candidate)
        elif query_lower in candidate_lower or candidate_lower in query_lower:
            matches.append(candidate)
        elif query_lower.replace("the", "") in candidate_lower:
            matches.append(candidate)
    
    return matches


def resolve_target(query: str, available_objects: List[str]) -> Optional[str]:
    """Resolve a natural language query to a single object name."""
    matches = fuzzy_match(query, available_objects)
    
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        return None
    return None


def find_matching_objects(query: str, available_objects: List[str]) -> List[str]:
    """Find all objects matching a query."""
    return fuzzy_match(query, available_objects)


def get_file_type(filepath: str) -> Optional[str]:
    """Determine file type from extension or content."""
    ext = Path(filepath).suffix.lower()
    
    dicom_exts = {'.dcm', '.dicom'}
    nifti_exts = {'.nii', '.nii.gz'}
    nrrd_exts = {'.nrrd', '.nhdr'}
    model_exts = {'.vtk', '.stl', '.obj', '.ply'}
    
    if ext in dicom_exts:
        return "DICOM"
    elif any(filepath.lower().endswith(e) for e in nifti_exts):
        return "NIfTI"
    elif ext in nrrd_exts:
        return "NRRD"
    elif ext in model_exts:
        return "MODEL"
    elif ext == '' or ext is None:
        return _detect_by_content(filepath)
    return None


def _detect_by_content(filepath: str) -> Optional[str]:
    """Detect file type by reading magic bytes."""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(256)
        
        if len(header) >= 132:
            if header[128:132] == b'DICM':
                return "DICOM"
        
        if len(header) >= 3:
            if header[:3] == b'\x1f\x8b\x08':
                return "NIfTI"
        
        if len(header) >= 4:
            if header[:4] in (b'<?xml', b'<VTK'):
                return "MODEL"
            if header[:4] == b'NRRD':
                return "NRRD"
        
        header_str = header[:128].decode('ascii', errors='ignore').lower()
        if '# vtk' in header_str or 'vtkdatafile' in header_str:
            return "MODEL"
        if 'itkversion' in header_str or 'nrrd' in header_str:
            return "NRRD"
        
        return None
    except Exception:
        return None


def scan_folder_for_files(folder_path: str) -> dict:
    """Scan a folder recursively and categorize supported files."""
    results = {
        "dicom_series": [],
        "nifti_files": [],
        "nrrd_files": [],
        "model_files": [],
        "other_files": []
    }
    
    if not isinstance(folder_path, str) or not os.path.isdir(folder_path):
        return results
    
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            filepath = os.path.join(root, file)
            if not isinstance(filepath, str):
                continue
            try:
                file_type = get_file_type(filepath)
            except Exception:
                file_type = None
            
            if file_type == "DICOM":
                results["dicom_series"].append(filepath)
            elif file_type == "NIfTI":
                results["nifti_files"].append(filepath)
            elif file_type == "NRRD":
                results["nrrd_files"].append(filepath)
            elif file_type == "MODEL":
                results["model_files"].append(filepath)
            else:
                results["other_files"].append(filepath)
    
    return results


def group_dicom_series(dicom_files: List[str]) -> List[List[str]]:
    """Group DICOM files into likely series (simple implementation)."""
    if not dicom_files:
        return []
    
    series = {}
    for filepath in dicom_files:
        if not isinstance(filepath, str):
            continue
        dir_name = os.path.dirname(filepath)
        if dir_name not in series:
            series[dir_name] = []
        series[dir_name].append(filepath)
    
    return list(series.values())


def format_scene_summary(summary: dict) -> str:
    """Format scene summary for LLM context."""
    lines = []
    
    for category, objects in summary.items():
        if objects:
            lines.append(f"{category.capitalize()}:")
            for obj in objects:
                vis = "visible" if obj.get("visible", True) else "hidden"
                opacity = f", opacity={obj.get('opacity')}" if obj.get("opacity") is not None else ""
                lines.append(f"  - {obj['name']} ({vis}{opacity})")
    
    return "\n".join(lines) if lines else "No objects in scene"