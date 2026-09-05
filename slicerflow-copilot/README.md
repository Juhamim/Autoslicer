# SlicerFlow Copilot 🧬

### *From Natural Language to Verified and Reproducible 3D Medical Imaging Workflows*

Built for Hackathon challenges **N34** (*Automated 3D Slicer Case Preparation Pipeline*) and **N35** (*AI-assisted automation of 3D Slicer workflows through natural-language interaction*).

---

## 💡 Core Philosophy

> **AI understands. Rules validate. 3D Slicer executes. Verification checks. Humans approve.**

SlicerFlow Copilot integrates directly into **3D Slicer's native GUI** and **Python Terminal Console**. It translates clinician natural language requests into structured, verified workflows while strictly enforcing security, technical validation, and human-in-the-loop oversight.

---

## 🏛️ Architecture & Control Flow

```text
               CLINICAL SCAN (NIfTI / NRRD / DICOM Series / Directory)
                                       ↓
                        CASE ANALYZER & DICOM METADATA
            (Dimensions, Voxel Spacing, Orientation, Modality, Tag Verification)
                                       ↓
                             NATURAL LANGUAGE PROMPT
             ("Prepare this CT scan, segment bone, and reconstruct a 3D model")
                                       ↓
         ┌────────────────────────────────────────────────────────────┐
         │                  SLICERFLOW COPILOT AGENT                  │
         │  ┌──────────────────────────────┐                         │
         │  │ Google Gemini API            │                         │
         │  │ (models/gemini-3.6-flash)    │                         │
         │  └──────────────┬───────────────┘                         │
         │                 │ (automatic fallback)                    │
         │  ┌──────────────▼───────────────┐                         │
         │  │ Deterministic Rule Engine    │                         │
         │  └──────────────────────────────┘                         │
         └─────────────────────────────┬──────────────────────────────┘
                                       ↓
                           STRUCTURED WORKFLOW PLAN
          [Inspect -> Load -> Preprocess -> Segment -> Model -> Validate -> Export]
                                       ↓
                         COMMAND & TOPOLOGY VALIDATOR
           (Whitelist check, topological ordering, input volume verification)
                                       ↓
                             [HUMAN APPROVAL GATE]
                                       ↓
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
   3D SLICER NATIVE GUI                               PYTHON TERMINAL REPL
   (MRML Scene, 3D Viewport, Segment Editor)          (CLI Agent, Standalone Script)
            └──────────────────────────┬──────────────────────────┘
                                       ↓
                             STEP-BY-STEP VERIFICATION
                    (Volume, Segmentation, Surface Mesh, Files)
                                       ↓
                             DELIVERABLES & PROVENANCE
            ├── 3D Surface Model (.stl / .obj in Slicer 3D Viewport)
            ├── SHA256 Reproducibility Manifest (manifest.json)
            └── Human-Readable Case Processing Audit Report (.md)
```

---

## ✨ Features

1. **Native 3D Slicer Extension (`MyExtension/MyModule`)**:
   - **Drag-and-Drop Drop Zone**: Drag clinical scans or DICOM directories directly into Slicer.
   - **Native File & Folder Browsers**: Pick `.nrrd`, `.nii`, `.nii.gz`, `.dcm`, or entire clinical DICOM study folders.
   - **Dedicated Chat-Like AI Agent**: Interactive conversational assistant right inside Slicer.
   - **Chain-of-Thought (CoT) Display**: Visualizes radiologist reasoning from Qwen 3.8.
   - **3D Viewport Camera Presets**: One-click orientation (`Anterior`, `Posterior`, `Lateral`, `Fit 3D View`).
   - **One-Click Scene Reset**: Clear scene and reload new cases cleanly.
   - **Direct Clipboard Export**: Copy the Markdown audit report directly to your clipboard.

2. **Python Terminal AI Agent (`agent.py`)**:
   - Run anywhere via `python agent.py` without requiring a browser or web server.
   - Interactive REPL with commands: `case <path>`, `inspect`, `code`, `run`, `report`, `manifest`.
   - Supports non-interactive CLI pipelines: `python agent.py --case scan.nrrd --query "Reconstruct 3D bone model" --exec`.

3. **In-Slicer Python Console Integration (`slicer_agent.py`)**:
   - Type directly inside 3D Slicer's built-in Python Interactor:
     ```python
     import slicer_agent as sf
     sf.load("C:/path/to/scan.nrrd")
     sf.chat("Prepare this CT scan and reconstruct the bone 3D model")
     sf.run()
     ```

4. **Google Gemini API LLM Integration**:
   - Powered by `models/gemini-3.6-flash` via official OpenAI-compatible endpoint.
   - Full streaming Chain-of-Thought (CoT) reasoning extraction.
   - Robust zero-failure fallback to offline deterministic rule engine.

5. **Diagnostic Safety Guardrails**:
   - Whitelist of 8 medical engineering operations (`inspect_case`, `load_volume`, `select_series`, `preprocess`, `segment`, `generate_model`, `validate`, `export`).
   - Intercepts and blocks diagnostic and prognostic queries ("diagnose cancer") with compliant explanations.

6. **Full Reproducibility Provenance**:
   - Generates cryptographic SHA256 hashes of input volumes.
   - Creates a structured `manifest.json` capturing execution parameters, timings, and outputs.
   - Generates a clinical markdown audit report.

---

## 📦 Distribution & Multi-Surface Access

SlicerFlow Copilot is designed with **zero web dependencies** and operates natively across 4 execution surfaces:

| Surface | Description | How to Launch |
| :--- | :--- | :--- |
| **Windows Standalone Executable** | Standalone native binary (`SlicerFlow.exe` / `sf.exe`) with all dependencies and DLLs bundled. No Python install required. | `.\SlicerFlow.exe` or `.\dist\SlicerFlow\SlicerFlow.exe` |
| **Global Windows CLI (`sf`)** | Universal command dispatcher accessible from any terminal window or PowerShell session. | `sf load <path>`, `sf chat "<prompt>"`, `sf run` |
| **Native 3D Slicer Extension** | Embedded Qt module (`AI Medical Workflows -> SlicerFlow Copilot`) inside 3D Slicer. | `sf --slicer` or `SlicerFlow.bat [1]` |
| **In-Slicer Python Console** | Direct programmatic bridge inside Slicer's Python Interactor (`Ctrl + \`). | `import slicer_agent as sf` |

---

## 🏛️ Complete 6-Phase Pipeline Architecture

- **Phase 1: Case Analyzer (`analyzer/case_analyzer.py`)**
  - Clinical volume inspection for NRRD, NIfTI, and DICOM study series.
  - Computes dimensions, voxel spacing, origin, intensity bounds (HU), and series count.
- **Phase 2: AI Copilot (`copilot/copilot_engine.py`, `copilot/llm_client.py`)**
  - Powered by **Google Gemini API** (`models/gemini-3.6-flash`) with streaming Chain-of-Thought (CoT) reasoning.
  - Zero-failure fallback to deterministic rule parser.
  - Strict whitelist of 8 operations (`inspect_case`, `load_volume`, `select_series`, `preprocess`, `segment`, `generate_model`, `validate`, `export`).
  - Strict rejection of diagnostic and clinical decision queries.
- **Phase 3: Slicer Automation Engine (`automation/slicer_executor.py`, `automation/code_generator.py`)**
  - Generates reproducible, auditable 3D Slicer Python automation scripts.
  - Direct headless or live MRML scene execution (Volume loading, Segment Editor thresholding, closed surface generation).
- **Phase 4: Output Validator & Manifest Manager (`validation/output_validator.py`, `validation/manifest_manager.py`)**
  - Verifies segmentation voxel coverage, volume bounds, and 3D surface mesh triangle counts.
  - Generates cryptographically hashed (`SHA256`) JSON reproducibility manifests (`*_manifest.json`).
- **Phase 5: Case Verification & Reporting (`reporting/report_generator.py`)**
  - Produces structured clinical Markdown case processing audit reports (`*_processing_report.md`).
- **Phase 6: Native Slicer Extension UI & Universal Executable Packaging**
  - Embedded Qt user interface with drag-and-drop zone, camera orientation presets, and live log view.
  - Standalone Windows executable compilation via PyInstaller (`dist/SlicerFlow/SlicerFlow.exe`).

---

## 🚀 Quick Start

### 1. Launch with Standalone Windows Executable
No Python installation or virtual environment configuration needed:
```powershell
# From repository root:
.\SlicerFlow.exe --help

# 1. Load clinical volume
.\SlicerFlow.exe load "C:\data\patient_ct.nrrd"

# 2. Ask AI Copilot in natural language
.\SlicerFlow.exe chat "Reconstruct 3D skull and mandible with bone thresholding"

# 3. View synthesized reproducible script
.\SlicerFlow.exe code

# 4. Execute pipeline and reconstruct 3D surface mesh
.\SlicerFlow.exe run

# 5. View audit report and manifest
.\SlicerFlow.exe report
.\SlicerFlow.exe manifest
```

### 2. Global Terminal CLI (`sf`)
The `sf` command is registered globally in Windows:
```powershell
sf load "C:\data\patient_ct.nrrd"
sf chat "Reconstruct bone 3D model"
sf run
sf report
```

### 3. Launch 3D Slicer Native GUI
```powershell
# Via standalone executable:
.\SlicerFlow.exe --slicer

# Or via batch launcher:
.\SlicerFlow.bat
```

---

## 💻 3D Slicer In-Console Commands

Inside 3D Slicer's Python Console (`Ctrl + \` or `View -> Python Interactor`):

```python
import slicer_agent as sf

# Inspect and load a scan
sf.load("C:/path/to/my_scan.nrrd")

# Ask SlicerFlow in natural language
sf.chat("Prepare this CT scan, segment bone, and reconstruct 3D surface model")

# View synthesized Slicer automation script
sf.code()

# Execute with human approval
sf.run()

# View audit report & manifest
sf.report()
sf.manifest()
```

---

## 🛡️ Safety & Clinical Disclaimer

> **SlicerFlow Copilot is a research and medical engineering workflow automation tool. It does NOT provide autonomous medical diagnosis, clinical prognostic predictions, or treatment decisions. All imaging outputs, segmentations, and 3D reconstructions require human review and approval by qualified medical professionals.**

---

## 🐛 Bug Fixes & Current State

All bugs have been fixed and verified. 12/12 tests passing.

### Fixed Issues
- **Gemini API Authentication**: Fixed `Authorization: Bearer` header for proper Gemini API communication
- **`is_configured()`**: Properly validates API keys instead of returning True for localhost
- **Streamlit Re-execution**: Fixed pipeline re-running on every page load
- **General Conversation**: `slicer_agent.py` chat() now handles general queries without requiring a case file
- **SegmentationValidator**: Fixed missing `arr` parameter in `orchestrator.py` `_exec_validate()`
- **`.env` Loading**: Fixed to load from project root directory (3 levels up)
- **Missing Modules**: Created `__init__.py` files, `volume_validator.py`, `segmentation_validator.py`, `output_validator.py`

### Build Artifacts
- `SlicerFlow.exe` (5 KB) - Native launcher
- `sf.exe` (5 KB) - CLI launcher  
- `SlicerFlow_Setup.exe` (22 KB) - Installer
- `dist/SlicerFlow/SlicerFlow.exe` (87 MB) - Standalone executable via PyInstaller
