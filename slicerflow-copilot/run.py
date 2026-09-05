"""SlicerFlow Copilot - Production Launcher.

Allows one-command launching of:
1. Python Terminal AI Agent (`python run.py --terminal` or default)
2. 3D Slicer Native GUI with SlicerFlow Copilot loaded (`python run.py --slicer`)
"""

import os
import sys
import subprocess
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
MODULE_DIR = os.path.join(ROOT_DIR, "MyExtension", "MyModule")
SLICER_EXE = r"C:\Users\juhai\AppData\Local\slicer.org\3D Slicer 5.12.3\Slicer.exe"


def launch_slicer():
    """Launch 3D Slicer with the SlicerFlow Copilot module."""
    if os.path.exists(SLICER_EXE):
        print(f"[+] Launching 3D Slicer with SlicerFlow Copilot: {SLICER_EXE}")
        cmd = [SLICER_EXE, "--additional-module-paths", MODULE_DIR]
        subprocess.Popen(cmd)
    else:
        print(f"[-] 3D Slicer executable not found at: {SLICER_EXE}")
        print("    Please start 3D Slicer manually or check your installation path.")


def launch_terminal_agent(case_path: str = ""):
    """Launch the interactive terminal AI Copilot."""
    agent_script = os.path.join(BASE_DIR, "agent.py")
    cmd = [sys.executable, agent_script]
    if case_path:
        cmd.extend(["--case", case_path])
    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(description="SlicerFlow Copilot Launcher")
    parser.add_argument("--slicer", action="store_true", help="Launch 3D Slicer GUI with SlicerFlow Copilot extension")
    parser.add_argument("--terminal", action="store_true", help="Launch Interactive Terminal AI Agent")
    parser.add_argument("--case", type=str, default="", help="Path to medical scan file")

    args = parser.parse_args()

    if args.slicer:
        launch_slicer()
    else:
        launch_terminal_agent(args.case)


if __name__ == "__main__":
    main()
