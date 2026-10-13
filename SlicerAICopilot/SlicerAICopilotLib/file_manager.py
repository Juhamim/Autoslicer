"""File Manager - Handles folder scanning and file import."""

import os
from typing import Dict, List, Optional, Any
from pathlib import Path

try:
    import slicer
    SLICER_AVAILABLE = True
except ImportError:
    SLICER_AVAILABLE = False
    slicer = None

from .utils import (
    scan_folder_for_files, group_dicom_series, get_file_type
)


class FileManager:
    """Manages file operations for the Copilot."""
    
    def __init__(self):
        self.last_scan_result = None
    
    def scan_folder(self, folder_path) -> Dict[str, Any]:
        """Scan a folder for supported medical imaging files."""
        if isinstance(folder_path, (list, tuple)):
            folder_path = folder_path[0] if folder_path else ""
        
        folder_path = str(folder_path) if folder_path else ""
        
        if not folder_path:
            return {"error": "No folder path provided"}
        
        if not os.path.exists(folder_path):
            return {"error": f"Folder not found: {folder_path}"}
        
        if not os.path.isdir(folder_path):
            return {"error": f"Not a directory: {folder_path}"}
        
        try:
            result = scan_folder_for_files(folder_path)
            result["dicom_series_groups"] = group_dicom_series(result["dicom_series"])
        except Exception as e:
            return {"error": f"Scan error: {str(e)}"}
        
        self.last_scan_result = result
        return result
    
    def get_detected_files_summary(self, scan_result: Dict = None) -> str:
        """Get a human-readable summary of detected files."""
        if scan_result is None:
            scan_result = self.last_scan_result
        
        if not scan_result or "error" in scan_result:
            return "No files scanned or error occurred"
        
        lines = ["Detected files:"]
        
        dicom_groups = scan_result.get("dicom_series_groups", [])
        if dicom_groups:
            lines.append(f"  + {len(dicom_groups)} DICOM series")
            for i, series in enumerate(dicom_groups):
                if isinstance(series, list):
                    lines.append(f"    Series {i+1}: {len(series)} files")
                else:
                    lines.append(f"    Series {i+1}: 1 file")
        
        nifti_files = scan_result.get("nifti_files", [])
        if nifti_files:
            lines.append(f"  + {len(nifti_files)} NIfTI files")
            for f in nifti_files[:5]:
                lines.append(f"    {os.path.basename(f)}")
            if len(nifti_files) > 5:
                lines.append(f"    ... and {len(nifti_files) - 5} more")
        
        nrrd_files = scan_result.get("nrrd_files", [])
        if nrrd_files:
            lines.append(f"  + {len(nrrd_files)} NRRD files")
            for f in nrrd_files[:5]:
                lines.append(f"    {os.path.basename(f)}")
        
        model_files = scan_result.get("model_files", [])
        if model_files:
            lines.append(f"  + {len(model_files)} model files")
            for f in model_files[:5]:
                lines.append(f"    {os.path.basename(f)}")
        
        other_files = scan_result.get("other_files", [])
        if other_files:
            lines.append(f"  - {len(other_files)} other files (not imported)")
        
        return "\n".join(lines)
    
    def import_case(self, scan_result: Dict = None, selections: Dict = None) -> Dict[str, Any]:
        """Import selected files from a scan result."""
        if scan_result is None:
            scan_result = self.last_scan_result
        
        if not scan_result or "error" in scan_result:
            return {"success": False, "error": "No valid scan result"}
        
        if not SLICER_AVAILABLE:
            return {"success": False, "error": "Slicer not available"}
        
        results = {
            "success": True,
            "imported": [],
            "failed": []
        }
        
        import slicer.util
        
        if selections is None:
            selections = {
                "dicom_series": list(range(len(scan_result.get("dicom_series_groups", [])))),
                "nifti_files": list(range(len(scan_result.get("nifti_files", [])))),
                "nrrd_files": list(range(len(scan_result.get("nrrd_files", [])))),
                "model_files": list(range(len(scan_result.get("model_files", [])))),
            }
        
        dicom_groups = scan_result.get("dicom_series_groups", [])
        for idx in selections.get("dicom_series", []):
            if 0 <= idx < len(dicom_groups):
                group = dicom_groups[idx]
                if not isinstance(group, list):
                    results["failed"].append(f"DICOM series {idx+1}: invalid group")
                    continue
                dir_path = os.path.dirname(group[0]) if group else None
                if not dir_path:
                    results["failed"].append(f"DICOM series {idx+1}: empty group")
                    continue
                loaded = self._load_dicom_folder(dir_path)
                if loaded:
                    results["imported"].append(f"DICOM series {idx+1}: {loaded}")
                else:
                    results["failed"].append(f"DICOM series {idx+1}: load failed")
        
        nifti_files = scan_result.get("nifti_files", [])
        for idx in selections.get("nifti_files", []):
            if 0 <= idx < len(nifti_files):
                try:
                    node = slicer.util.loadVolume(nifti_files[idx])
                    if node:
                        results["imported"].append(f"NIfTI: {node.GetName()}")
                    else:
                        results["failed"].append(f"NIfTI {idx}: Failed to load")
                except Exception as e:
                    results["failed"].append(f"NIfTI {idx}: {str(e)}")
        
        nrrd_files = scan_result.get("nrrd_files", [])
        for idx in selections.get("nrrd_files", []):
            if 0 <= idx < len(nrrd_files):
                try:
                    node = slicer.util.loadVolume(nrrd_files[idx])
                    if node:
                        results["imported"].append(f"NRRD: {node.GetName()}")
                    else:
                        results["failed"].append(f"NRRD {idx}: Failed to load")
                except Exception as e:
                    results["failed"].append(f"NRRD {idx}: {str(e)}")
        
        model_files = scan_result.get("model_files", [])
        for idx in selections.get("model_files", []):
            if 0 <= idx < len(model_files):
                try:
                    node = slicer.util.loadModel(model_files[idx])
                    if node:
                        results["imported"].append(f"Model: {node.GetName()}")
                    else:
                        results["failed"].append(f"Model {idx}: Failed to load")
                except Exception as e:
                    results["failed"].append(f"Model {idx}: {str(e)}")
        
        if results["failed"]:
            results["success"] = False
        
        return results
    
    def _load_dicom_folder(self, dir_path):
        """Load DICOM files from a folder using multiple fallback methods."""
        try:
            import slicer
            dicom_plugin = slicer.modules.dicom
            if dicom_plugin and hasattr(dicom_plugin, 'logic'):
                logic = dicom_plugin.logic
                if hasattr(logic, 'examineForLoad'):
                    loadable_list = logic.examineForLoad([dir_path])
                    if loadable_list:
                        for loadable in loadable_list:
                            if hasattr(loadable, 'files') and loadable.files:
                                success = logic.loadLoadable(loadable)
                                if success:
                                    return f"{len(loadable.files)} files loaded"
        except Exception:
            pass
        
        try:
            import slicer
            dicom_plugin = slicer.modules.dicom
            if dicom_plugin and hasattr(dicom_plugin, 'logic'):
                logic = dicom_plugin.logic
                if hasattr(logic, 'loadDirectory'):
                    success = logic.loadDirectory(dir_path)
                    if success:
                        return "Directory loaded"
        except Exception:
            pass
        
        try:
            import slicer
            dicom_plugin = slicer.modules.dicom
            if dicom_plugin and hasattr(dicom_plugin, 'crawler'):
                dicom_plugin.crawler.crawl([dir_path])
                return "DICOM database updated"
        except Exception:
            pass
        
        try:
            import slicer.util
            for fname in os.listdir(dir_path):
                fpath = os.path.join(dir_path, fname)
                if os.path.isfile(fpath):
                    try:
                        node = slicer.util.loadNodeFromFile(fpath)
                        if node:
                            return f"Loaded: {node.GetName()}"
                    except Exception:
                        continue
        except Exception:
            pass
        
        return None


_file_manager_instance = None


def get_file_manager() -> FileManager:
    """Get the global file manager instance."""
    global _file_manager_instance
    if _file_manager_instance is None:
        _file_manager_instance = FileManager()
    return _file_manager_instance