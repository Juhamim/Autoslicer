"""3D Slicer In-Console AI Agent Bridge (Google Gemini AI & Direct Scene Execution).

Enables natural language control directly inside 3D Slicer's Python Console or any terminal.
Commands:
    import slicer_agent as sf
    sf.load("C:/path/to/scan.nrrd")
    sf.chat("Prepare this CT scan and reconstruct the bone 3D model")
    sf.run()
    sf.code()
    sf.report()
    sf.start()   # Starts interactive chat loop
"""

import os
import sys
import json
from typing import Optional, Dict, Any

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure slicerflow package is on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Resolve shared project outputs folder even when running from frozen PyInstaller bundle
OUTPUTS_DEFAULT = os.path.join(BASE_DIR, "outputs")
cur = BASE_DIR
for _ in range(4):
    test_out = os.path.join(cur, "slicerflow-copilot", "outputs")
    if os.path.isdir(test_out) and "dist" not in cur:
        OUTPUTS_DEFAULT = test_out
        break
    parent = os.path.dirname(cur)
    if parent == cur:
        break
    cur = parent

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from copilot.parser import RuleBasedParser
from copilot.planner import WorkflowPlanner
from copilot.llm_client import ExternalLLMClient
from analyzer.case_analyzer import CaseAnalyzer
from analyzer.metadata import CaseMetadata
from validation.command_validator import CommandValidator
from automation.code_generator import SlicerCodeGenerator
from core.workflow import WorkflowPlan, OperationStatus


class SlicerLiveAgent:
    """Live AI Agent for 3D Slicer's Python Console and Terminal powered by Google Gemini API."""

    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = output_dir or OUTPUTS_DEFAULT
        os.makedirs(self.output_dir, exist_ok=True)
        self.llm_client = ExternalLLMClient()
        self.active_case: str = ""
        self.active_metadata: Optional[CaseMetadata] = None
        self.current_plan: Optional[WorkflowPlan] = None
        self.is_in_slicer = False
        self._check_slicer_env()

    def _check_slicer_env(self):
        try:
            import slicer
            if hasattr(slicer, "app") and slicer.app is not None and type(slicer.app).__name__ != "_SlicerMock":
                self.is_in_slicer = True
            elif hasattr(slicer, "mrmlScene") and slicer.mrmlScene is not None and type(slicer.mrmlScene).__name__ != "_SlicerMock":
                self.is_in_slicer = True
            else:
                self.is_in_slicer = False
        except (ImportError, AttributeError):
            self.is_in_slicer = False

    # 3D model file extensions
    MODEL_EXTENSIONS = {".vtk", ".stl", ".obj", ".ply", ".vtp", ".vtu", ".g", ".byu", ".off"}

    def load(self, case_path: str) -> bool:
        """Load and inspect a medical case (.nrrd, .nii, .nii.gz, .dcm, or DICOM folder) or 3D model (.vtk, .stl, .obj, etc.)."""
        clean_path = case_path.strip().strip('"').strip("'")
        if not os.path.exists(clean_path):
            print(f"[-] Case file not found: {clean_path}")
            return False

        self.active_case = clean_path

        # Check if this is a 3D model file or a directory of models
        is_model = False
        model_files = []

        if os.path.isdir(clean_path):
            for f in os.listdir(clean_path):
                ext = os.path.splitext(f.lower())[1]
                if ext in self.MODEL_EXTENSIONS:
                    model_files.append(os.path.join(clean_path, f))
            is_model = len(model_files) > 0
        else:
            ext = os.path.splitext(clean_path.lower())[1]
            is_model = ext in self.MODEL_EXTENSIONS
            if is_model:
                model_files = [clean_path]

        if is_model:
            return self._load_models(clean_path, model_files)

        # Standard volume loading
        self.active_metadata = CaseAnalyzer.analyze_case(clean_path)
        meta = self.active_metadata

        print(f"\n[+] Case Loaded: {meta.file_name}")
        print(f"    Format:     {meta.file_format} | Modality: {meta.modality}")
        if meta.dimensions:
            print(f"    Dimensions: {meta.dimensions[0]} x {meta.dimensions[1]} x {meta.dimensions[2]}")
        if meta.spacing:
            print(f"    Spacing:    {meta.spacing[0]:.2f} x {meta.spacing[1]:.2f} x {meta.spacing[2]:.2f} mm")
        if meta.intensity_min is not None:
            print(f"    Intensity:  [{meta.intensity_min:.1f}, {meta.intensity_max:.1f}] HU")
        print(f"    Status:     {meta.status}")

        if self.is_in_slicer:
            try:
                import slicer
                is_m_dir, m_files = self._is_model_directory(clean_path)
                if is_m_dir:
                    for mf in m_files:
                        slicer.util.loadModel(mf)
                    print("    [✓] Loaded 3D models into 3D Slicer MRML Scene")
                elif self._is_model_file(clean_path):
                    slicer.util.loadModel(clean_path)
                    print("    [✓] Loaded 3D model into 3D Slicer MRML Scene")
                else:
                    vol_node = slicer.util.loadVolume(clean_path)
                    if vol_node:
                        slicer.util.resetSliceViews()
                        print("    [✓] Loaded volume into 3D Slicer MRML Scene")
            except Exception as e:
                print(f"    [!] Slicer MRML load warning: {str(e)}")

        return True

    def _load_models(self, path: str, model_files: list) -> bool:
        """Load 3D model file(s) into Slicer or report metadata for CLI."""
        is_dir = os.path.isdir(path)
        dir_or_file = os.path.basename(path)

        if is_dir:
            print(f"\n[+] 3D Mesh Directory Loaded: {dir_or_file}")
            print(f"    Contains: {len(model_files)} model file(s)")
        else:
            print(f"\n[+] 3D Model Loaded: {dir_or_file}")

        for mf in sorted(model_files):
            fname = os.path.basename(mf)
            ext = os.path.splitext(fname)[1].upper()
            print(f"    - {fname} ({ext})")

        if self.is_in_slicer:
            import slicer
            loaded = 0
            for mf in sorted(model_files):
                try:
                    model_node = slicer.util.loadModel(mf)
                    if model_node:
                        pd = model_node.GetPolyData()
                        nv = pd.GetNumberOfPoints() if pd else 0
                        nf = pd.GetNumberOfCells() if pd else 0
                        print(f"    [✓] {os.path.basename(mf)}: {nv:,} vertices, {nf:,} faces")
                        loaded += 1
                except Exception as e:
                    print(f"    [!] Failed to load {os.path.basename(mf)}: {e}")

            # Reset 3D camera
            try:
                lm = slicer.app.layoutManager()
                if lm:
                    lm.threeDWidget(0).threeDView().resetCamera()
            except Exception:
                pass

            print(f"    [✓] Loaded {loaded}/{len(model_files)} models into 3D Slicer")
        else:
            print("    [i] Models detected. Use 'sf --slicer' to visualize in 3D Slicer.")

        return True

    def chat(self, user_query: str, case_path: Optional[str] = None, auto_execute: bool = False) -> bool:
        """Process a natural language request directly with Qwen 3.8 / Rule Engine."""
        print(f"\n[SlicerFlow Copilot] Received: '{user_query}'")

        if case_path:
            self.load(case_path)

        active_case = self.active_case
        if not isinstance(active_case, str):
            active_case = ""

        # If in Slicer and no path given, check active volume node in scene
        if self.is_in_slicer and not active_case:
            import slicer
            first_vol = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
            if first_vol and hasattr(first_vol, "GetStorageNode") and first_vol.GetStorageNode():
                storage = first_vol.GetStorageNode()
                if hasattr(storage, "GetFileName"):
                    fname = storage.GetFileName()
                    if isinstance(fname, str) and fname:
                        active_case = fname
                        self.active_case = fname

        if not active_case:
            if self.is_in_slicer:
                import slicer
                first_vol = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
                if not first_vol:
                    print("[-] No medical volume found in Slicer scene. Load or drop a case first.")
                    return False
            else:
                print("[-] No medical case specified. Provide a case path: sf.load('/path/to/scan.nrrd')")
                return False

        # Case metadata if available
        meta_dict = self.active_metadata.to_dict() if self.active_metadata else None
        if not meta_dict and active_case and os.path.exists(active_case):
            self.active_metadata = CaseAnalyzer.analyze_case(active_case)
            meta_dict = self.active_metadata.to_dict()

        # 1. AI Parse (Google Gemini AI with rule fallback)
        if self.llm_client.is_configured():
            print(f"[*] Parsing with Google Gemini AI ({self.llm_client.model_name})...")
            intent = self.llm_client.parse_workflow(user_query, case_metadata=meta_dict)
        else:
            print("[*] Parsing with SlicerFlow Deterministic Rule Engine...")
            intent = RuleBasedParser.parse(user_query, context=meta_dict)

        if intent.reasoning:
            print(f"\n[🧠 AI Radiologist Reasoning]:\n{intent.reasoning}\n")

        if not intent.is_supported:
            print("\n[!] UNSUPPORTED REQUEST REJECTED:")
            print(intent.unsupported_reason)
            return False

        # Handle general conversation & Q&A queries naturally without creating a workflow plan
        if intent.intent in ("general_conversation", "qa", "general_query") or not intent.operations:
            print(f"\n[🤖 SlicerFlow Copilot]:\n{intent.explanation}\n")
            return True

        # 2. Plan
        case_id = os.path.splitext(os.path.basename(active_case))[0] if active_case else "CASE_001"
        planner = WorkflowPlanner()
        plan = planner.plan(
            intent=intent,
            case_id=case_id,
            case_file_path=active_case
        )
        self.current_plan = plan
        try:
            cache_file = os.path.join(self.output_dir, ".plan_cache.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(plan.to_dict(), f, indent=2)
        except Exception:
            pass

        # 3. Validate
        is_valid, messages, _ = CommandValidator.validate_plan(plan, file_path=active_case)
        if not is_valid:
            print(f"[!] Validation blocked: {'; '.join(messages)}")
            return False

        print(f"[+] Plan Validated ({len(plan.steps)} operations): {' -> '.join(plan.operations_list())}")
        print("    Type sf.run() to execute or sf.code() to inspect synthesized Slicer script.")

        if auto_execute:
            return self.run()

        return True

    def _ensure_plan(self):
        if not self.current_plan:
            cache_file = os.path.join(self.output_dir, ".plan_cache.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.current_plan = WorkflowPlan.from_dict(data)
                except Exception:
                    pass

    def plan(self, user_query: str, case_path: Optional[str] = None) -> Optional[WorkflowPlan]:
        """Create and validate plan without auto-executing."""
        if self.chat(user_query, case_path=case_path, auto_execute=False):
            return self.current_plan
        return None

    def code(self):
        """Display the synthesized 3D Slicer Python script for the current plan."""
        self._ensure_plan()
        if not self.current_plan:
            print("[-] No active plan. Call sf.chat(...) first.")
            return
        script = SlicerCodeGenerator.generate_slicer_script(
            plan=self.current_plan,
            input_file_path=self.active_case,
            output_dir=self.output_dir
        )
        print("\n--- Synthesized 3D Slicer Python Script ---")
        print(script)
        print("-------------------------------------------\n")

    def run(self) -> bool:
        """Execute the current validated workflow plan."""
        self._ensure_plan()
        if not self.current_plan:
            if self.active_case:
                print("[*] No custom plan active. Synthesizing default bone prep & 3D reconstruction workflow...")
                self.chat("Prepare this CT scan and reconstruct the bone 3D model", auto_execute=False)
            else:
                print("[-] No case loaded and no plan active. Call sf.load('/path/to/scan') first.")
                return False

        plan = self.current_plan
        if not plan:
            return False

        if self.is_in_slicer:
            return self._execute_in_live_slicer(plan, self.active_case)
        else:
            print("[i] Executing via SlicerFlow Orchestration Engine...")
            from core.orchestrator import PipelineOrchestrator
            orch = PipelineOrchestrator()
            res = orch.execute(plan, self.active_case, self.output_dir)
            if res.final_status == OperationStatus.SUCCESS:
                print(f"[+] Pipeline Completed Successfully! Outputs saved to {self.output_dir}")
                self.report()
                return True
            else:
                print(f"[-] Pipeline finished with status: {res.final_status.value}")
                return False

    def report(self):
        """Display generated Case Processing Report."""
        case_id = self.current_plan.case_id if self.current_plan else (
            os.path.splitext(os.path.basename(self.active_case))[0] if self.active_case else "CASE"
        )
        report_path = os.path.join(self.output_dir, f"{case_id}_processing_report.md")
        if os.path.exists(report_path):
            print(f"\n--- Case Processing Audit Report ({report_path}) ---")
            with open(report_path, "r", encoding="utf-8") as f:
                print(f.read())
            print("-------------------------------------------------------\n")
        else:
            print("[-] No report found yet. Run a workflow first.")

    def manifest(self):
        """Display generated Provenance Manifest."""
        case_id = self.current_plan.case_id if self.current_plan else (
            os.path.splitext(os.path.basename(self.active_case))[0] if self.active_case else "CASE"
        )
        manifest_path = os.path.join(self.output_dir, f"{case_id}_manifest.json")
        if os.path.exists(manifest_path):
            print(f"\n--- Reproducibility Manifest ({manifest_path}) ---")
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(json.dumps(data, indent=2))
            print("---------------------------------------------------\n")
        else:
            print("[-] No manifest found yet. Run a workflow first.")

    def reset(self):
        """Reset scene and active state."""
        if self.is_in_slicer:
            try:
                import slicer
                slicer.mrmlScene.Clear(0)
                print("[✓] 3D Slicer MRML Scene cleared.")
            except Exception:
                pass
        self.active_case = ""
        self.active_metadata = None
        self.current_plan = None
        print("[✓] SlicerFlow Copilot state reset.")

    def _execute_in_live_slicer(self, plan: WorkflowPlan, input_file: str) -> bool:
        """Manipulate the live 3D Slicer MRML Scene directly."""
        import slicer

        try:
            # 1. Load Volume or Models if not already in scene
            vol_node = None
            if input_file:
                is_m_dir, m_files = self._is_model_directory(input_file)
                if is_m_dir:
                    print(f"[*] Loading {len(m_files)} 3D models from folder: {input_file}...")
                    for mf in m_files:
                        slicer.util.loadModel(mf)
                    print("[✓] 3D Models loaded into scene.")
                    return True
                elif self._is_model_file(input_file):
                    print(f"[*] Loading 3D model: {input_file}...")
                    slicer.util.loadModel(input_file)
                    print("[✓] 3D Model loaded into scene.")
                    return True
                else:
                    print(f"[*] Loading volume from: {input_file}...")
                    vol_node = slicer.util.loadVolume(input_file)
            else:
                vol_node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")

            if not vol_node:
                print("[-] No volume node available in Slicer MRML scene.")
                return False

            # Reset 2D slice views
            slicer.util.resetSliceViews()

            # 2. Extract parameters
            seg_step = plan.get_step("segment")
            anatomy = seg_step.parameters.get("target_anatomy", "bone") if seg_step else "bone"
            lower_th = float(seg_step.parameters.get("lower_threshold", 250.0)) if seg_step else 250.0
            upper_th = float(seg_step.parameters.get("upper_threshold", 2000.0)) if seg_step else 2000.0

            # 3. Segmentation
            print(f"[*] Creating segmentation for {anatomy} (HU [{lower_th:.0f}, {upper_th:.0f}])...")
            seg_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", f"SlicerFlow_{anatomy.title()}")
            seg_node.CreateDefaultDisplayNodes()
            seg_node.SetReferenceImageGeometryParameterFromVolumeNode(vol_node)

            segment_id = seg_node.GetSegmentation().AddEmptySegment(anatomy)

            # Use SegmentEditor
            editor_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
            widget = slicer.qMRMLSegmentEditorWidget()
            widget.setMRMLScene(slicer.mrmlScene)
            widget.setMRMLSegmentEditorNode(editor_node)
            widget.setSegmentationNode(seg_node)
            widget.setSourceVolumeNode(vol_node)
            widget.setCurrentSegmentID(segment_id)

            widget.setActiveEffectByName("Threshold")
            effect = widget.activeEffect()
            if effect:
                effect.setParameter("MinimumThreshold", str(lower_th))
                effect.setParameter("MaximumThreshold", str(upper_th))
                effect.self().onApply()

            # Clean up editor
            slicer.mrmlScene.RemoveNode(editor_node)

            # 4. Generate 3D Representation
            print("[*] Generating closed 3D surface mesh in Slicer 3D View...")
            seg_node.CreateClosedSurfaceRepresentation()

            # Reset 3D view camera
            layout_manager = slicer.app.layoutManager()
            if layout_manager:
                three_d_view = layout_manager.threeDWidget(0).threeDView()
                if three_d_view:
                    three_d_view.resetCamera()

            # 5. Export
            stl_path = os.path.join(self.output_dir, f"{plan.case_id}_{anatomy}.stl")
            slicer.modules.segmentations.logic().ExportSegmentsClosedSurfaceRepresentationToFiles(
                self.output_dir,
                seg_node,
                None,
                "STL"
            )
            print(f"[+] Completed! 3D Model visible in Slicer 3D view and exported to {stl_path}")
            return True

        except Exception as e:
            print(f"[-] Live Slicer execution failed: {str(e)}")
            return False


# Global default agent instance
_default_agent = SlicerLiveAgent()


def load(case_path: str) -> bool:
    """Load a medical case (.nrrd, .nii, .dcm)."""
    return _default_agent.load(case_path)


def chat(query: str, case_path: Optional[str] = None, auto_execute: bool = False) -> bool:
    """Process a natural language request."""
    return _default_agent.chat(query, case_path, auto_execute=auto_execute)


def ask(query: str, case_path: Optional[str] = None) -> bool:
    """Alias for chat."""
    return chat(query, case_path)


def plan(query: str, case_path: Optional[str] = None) -> Optional[WorkflowPlan]:
    """Create and validate plan without executing."""
    return _default_agent.plan(query, case_path)


def run() -> bool:
    """Execute active workflow plan."""
    return _default_agent.run()


def code():
    """Display synthesized 3D Slicer Python script."""
    _default_agent.code()


def report():
    """Display processing audit report."""
    _default_agent.report()


def manifest():
    """Display reproducibility manifest."""
    _default_agent.manifest()


def reset():
    """Reset scene and agent state."""
    _default_agent.reset()


def inspect():
    """Display metadata inspection of active case."""
    if _default_agent.active_metadata:
        _default_agent.load(_default_agent.active_case)
    else:
        print("[-] No case loaded. Call sf.load('/path/to/scan') first.")


def start():
    """Start interactive terminal REPL inside Python Console."""
    from agent import TerminalAIAgent
    agent = TerminalAIAgent(case_path=_default_agent.active_case)
    agent.interactive_repl()
