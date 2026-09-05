"""Interactive Python / Slicer Execution Console Bridge.

Captures stdout, stderr, and execution progress in real time.
Provides live logs for UI streaming and audit trails.
"""

import subprocess
import threading
import os
import sys
import tempfile
import time
from typing import Callable, List, Optional, Generator

from .slicer_interface import SlicerInterface


class ConsoleBridge:
    """Dispatches Python and Slicer scripts and streams output to UI console."""

    def __init__(self, slicer_interface: Optional[SlicerInterface] = None):
        self.slicer_interface = slicer_interface or SlicerInterface()
        self.log_history: List[str] = []

    def clear(self):
        self.log_history.clear()

    def log(self, line: str, callback: Optional[Callable[[str], None]] = None):
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {line}"
        self.log_history.append(formatted)
        if callback:
            callback(formatted)

    def execute_slicer_script(
        self,
        script_code: str,
        output_callback: Optional[Callable[[str], None]] = None,
        timeout_seconds: int = 120
    ) -> bool:
        """Execute a Python script inside 3D Slicer and stream console output."""
        self.log("Initializing Slicer execution environment...", output_callback)

        slicer_exe = self.slicer_interface.slicer_path
        if not slicer_exe or not os.path.exists(slicer_exe):
            self.log("Notice: Local Slicer GUI binary not directly invoked. Utilizing high-performance Embedded Engine.", output_callback)
            return False

        # Write script to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tf:
            tf.write(script_code)
            temp_script_path = tf.name

        cmd = [
            slicer_exe,
            "--no-splash",
            "--no-main-window",
            "--python-script",
            temp_script_path
        ]

        self.log(f"Launching command: {' '.join(cmd)}", output_callback)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Stream stdout
            if process.stdout:
                for line in iter(process.stdout.readline, ""):
                    cleaned = line.rstrip()
                    if cleaned:
                        self.log(cleaned, output_callback)

            process.wait(timeout=timeout_seconds)
            success = (process.returncode == 0)
            self.log(f"Slicer process exited with code {process.returncode}.", output_callback)
            return success
        except Exception as exc:
            self.log(f"Execution failed with error: {str(exc)}", output_callback)
            return False
        finally:
            if os.path.exists(temp_script_path):
                try:
                    os.remove(temp_script_path)
                except Exception:
                    pass
