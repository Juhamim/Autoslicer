"""3D Slicer Interface and Environment Locator.

Detects 3D Slicer installation and provides execution hooks for headless execution.
"""

import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any


class SlicerInterface:
    """Interacts with 3D Slicer executable and Python environment."""

    DEFAULT_WINDOWS_PATHS = [
        r"C:\Users\juhai\AppData\Local\slicer.org\3D Slicer 5.12.3\Slicer.exe",
        r"C:\Users\juhai\AppData\Local\slicer.org\3D Slicer 5.12.3\bin\PythonSlicer.exe",
        r"C:\Program Files\Slicer 5.12.3\Slicer.exe",
        r"C:\Program Files\Slicer 5.12.3\bin\PythonSlicer.exe",
    ]

    def __init__(self, custom_path: Optional[str] = None):
        self.slicer_path = self._find_slicer(custom_path)
        self.python_slicer_path = self._find_python_slicer()

    def _find_slicer(self, custom_path: Optional[str] = None) -> Optional[str]:
        if custom_path and os.path.exists(custom_path):
            return custom_path

        env_path = os.environ.get("SLICER_PATH")
        if env_path and os.path.exists(env_path):
            return env_path

        which_slicer = shutil.which("Slicer")
        if which_slicer:
            return which_slicer

        for p in self.DEFAULT_WINDOWS_PATHS:
            if os.path.exists(p) and p.endswith("Slicer.exe"):
                return p

        # Check local AppData dynamically
        appdata_local = os.environ.get("LOCALAPPDATA", "")
        if appdata_local:
            slicer_org = Path(appdata_local) / "slicer.org"
            if slicer_org.exists():
                for exe in slicer_org.glob("**/Slicer.exe"):
                    return str(exe)

        return None

    def _find_python_slicer(self) -> Optional[str]:
        if self.slicer_path:
            slicer_dir = os.path.dirname(self.slicer_path)
            candidate1 = os.path.join(slicer_dir, "bin", "PythonSlicer.exe")
            if os.path.exists(candidate1):
                return candidate1
            candidate2 = os.path.join(slicer_dir, "PythonSlicer.exe")
            if os.path.exists(candidate2):
                return candidate2

        for p in self.DEFAULT_WINDOWS_PATHS:
            if os.path.exists(p) and "PythonSlicer" in p:
                return p

        return None

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_available": bool(self.slicer_path or self.python_slicer_path),
            "slicer_executable": self.slicer_path,
            "python_slicer_executable": self.python_slicer_path,
            "version": "5.12.3" if (self.slicer_path and "5.12" in self.slicer_path) else "Detected",
        }
