"""SlicerFlow Copilot - All-In-One Universal CLI Dispatcher.

Handles:
- Natural CLI commands: sf load <path>, sf chat <prompt>, sf run, sf code, sf report
- Method-syntax CLI commands: sf.load("path"), sf.run(), sf.chat("prompt")
- Slicer GUI launcher: sf --slicer, sf gui
- Interactive REPL: sf
"""

import os
import sys
import json
import re
import subprocess
from typing import Optional, Dict, Any

if getattr(sys, "frozen", False):
    EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    cur = EXE_DIR
    found_base = None
    for _ in range(4):
        if os.path.isdir(os.path.join(cur, "slicerflow-copilot")):
            found_base = cur
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    BASE_DIR = found_base or getattr(sys, "_MEIPASS", EXE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

COPILOT_DIR = os.path.join(BASE_DIR, "slicerflow-copilot")
if COPILOT_DIR not in sys.path:
    sys.path.insert(0, COPILOT_DIR)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

SESSION_FILE = os.path.join(COPILOT_DIR, "outputs", ".session.json")
SLICER_EXE = r"C:\Users\juhai\AppData\Local\slicer.org\3D Slicer 5.12.3\Slicer.exe"
MODULE_DIR = os.path.join(BASE_DIR, "MyExtension", "MyModule")


def get_session() -> Dict[str, Any]:
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active_case": ""}


def save_session(session: Dict[str, Any]):
    os.makedirs(os.path.dirname(SESSION_FILE), exist_ok=True)
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2)
    except Exception:
        pass


def launch_slicer():
    if os.path.exists(SLICER_EXE):
        print(f"[+] Launching 3D Slicer with SlicerFlow Copilot: {SLICER_EXE}")
        subprocess.Popen([SLICER_EXE, "--additional-module-paths", MODULE_DIR])
    else:
        print(f"[-] 3D Slicer not found at: {SLICER_EXE}")


def clean_arg(arg: str) -> str:
    # strip parens, quotes, etc: ("C:/path") -> C:/path
    arg = arg.strip()
    match = re.search(r'[\'"]([^\'"]+)[\'"]', arg)
    if match:
        return match.group(1)
    return arg.strip("()\"' ")


def print_help():
    print("""
=======================================================================
             SLICERFLOW COPILOT - UNIVERSAL NATIVE CLI
   Natural Language -> Validated Workflow -> Automated 3D Pipeline
=======================================================================

Usage:
  sf                              Start interactive Terminal AI Copilot Agent
  sf <prompt>                     Ask AI Copilot to plan or inspect
  sf chat "<prompt>"              Plan medical imaging workflow via AI
  sf load <path>                  Inspect and load DICOM/NRRD/NIfTI volume
  sf run                          Execute workflow pipeline in 3D Slicer
  sf code                         Display generated reproducible Python script
  sf report                       Show execution validation and audit report
  sf manifest                     View JSON case metadata & reproducibility manifest
  sf inspect                      Display detailed clinical volume metadata
  sf reset                        Clear active session
  sf --slicer, sf gui             Launch native 3D Slicer with Copilot Module
  sf --help, sf -h                Show this help message

Examples:
  sf load "C:\\data\\patient_ct.nrrd"
  sf chat "Reconstruct 3D skull and mandible with bone thresholding"
  sf run
  sf report
""")


def main():
    args = sys.argv[1:]
    session = get_session()

    if not args:
        # Launch interactive REPL
        from agent import TerminalAIAgent
        agent = TerminalAIAgent(case_path=session.get("active_case", ""))
        agent.interactive_repl()
        return

    full_cmd = " ".join(args).strip()

    # Help
    if full_cmd in ("--help", "-h", "help", "/?"):
        print_help()
        return

    # Slicer GUI
    if full_cmd in ("--slicer", "-s", "gui", "slicer"):
        launch_slicer()
        return

    import slicer_agent as sf

    # Restore session case
    if session.get("active_case"):
        sf.load(session["active_case"])

    # Match .load("path") or load path
    if full_cmd.startswith(".load") or full_cmd.startswith("load"):
        param = re.sub(r'^\.?load[\s\(]*', '', full_cmd).rstrip(')')
        clean_path = clean_arg(param)
        if sf.load(clean_path):
            session["active_case"] = clean_path
            save_session(session)
        return

    # Match .run() or run
    if full_cmd in (".run()", "run()", ".run", "run", "exec"):
        sf.run()
        return

    # Match .code() or code
    if full_cmd in (".code()", "code()", ".code", "code"):
        sf.code()
        return

    # Match .report() or report
    if full_cmd in (".report()", "report()", ".report", "report"):
        sf.report()
        return

    # Match .manifest() or manifest
    if full_cmd in (".manifest()", "manifest()", ".manifest", "manifest"):
        sf.manifest()
        return

    # Match .inspect() or inspect
    if full_cmd in (".inspect()", "inspect()", ".inspect", "inspect"):
        sf.inspect()
        return

    # Match .reset() or reset
    if full_cmd in (".reset()", "reset()", ".reset", "reset"):
        sf.reset()
        session["active_case"] = ""
        save_session(session)
        return

    # Match .chat("query") or chat query or query
    query = full_cmd
    if query.startswith(".chat") or query.startswith("chat"):
        query = re.sub(r'^\.?chat[\s\(]*', '', query).rstrip(')')
    query = clean_arg(query)

    sf.chat(query)


if __name__ == "__main__":
    main()
