"""SlicerFlow Copilot - 3D Slicer Native Extension Module.

Provides:
1. Native Drag-and-Drop & File Browser for medical scans (.nrrd, .nii, .nii.gz, .dcm, DICOM folders, .vtk, .stl).
2. Dedicated Chat-Like AI Agent Interface powered by Google Gemini API & Rule Engine.
3. Live Chain-of-Thought (CoT) reasoning display from the radiologist AI model.
4. Automated Slicer MRML scene manipulation, 3D segmentation, surface mesh reconstruction,
   camera viewport orientation presets, and reproducible provenance manifests.
"""

import os
import sys
import logging
from typing import Optional, Dict, Any, List

import vtk
import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleWidget,
    ScriptedLoadableModuleLogic,
)
import qt
import ctk

# Ensure slicerflow-copilot is on path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COPILOT_DIR = os.path.join(BASE_DIR, "slicerflow-copilot")
if COPILOT_DIR not in sys.path:
    sys.path.insert(0, COPILOT_DIR)

# Import SlicerFlow Copilot core modules
from core.operation_registry import get_supported_operations, is_supported_operation  # type: ignore
from core.workflow import WorkflowPlan, WorkflowStep, OperationStatus  # type: ignore
from copilot.parser import RuleBasedParser  # type: ignore
from copilot.planner import WorkflowPlanner  # type: ignore
from copilot.llm_client import ExternalLLMClient  # type: ignore
from analyzer.case_analyzer import CaseAnalyzer  # type: ignore
from analyzer.metadata import CaseMetadata  # type: ignore
from validation.command_validator import CommandValidator  # type: ignore
from automation.code_generator import SlicerCodeGenerator  # type: ignore
from reporting.manifest import ManifestGenerator  # type: ignore
from reporting.report import ReportGenerator  # type: ignore


#
# Module Definition
#
class MyModule(ScriptedLoadableModule):
    """SlicerFlow Copilot scripted loadable module."""

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("SlicerFlow Copilot")
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "AI Medical Workflows")]
        self.parent.dependencies = []
        self.parent.contributors = ["SlicerFlow Copilot Team"]
        self.parent.helpText = _("""
Natural Language to Verified & Reproducible 3D Medical Imaging Workflows.
Combines Automated Case Preparation (N34) and AI Slicer Copilot (N35).
""")
        self.parent.acknowledgementText = _("""
Powered by 3D Slicer, Google Gemini API (models/gemini-3.6-flash), and SimpleITK.
""")


try:
    _BaseFrame = qt.QFrame
except (AttributeError, NameError):
    _BaseFrame = object


class DragDropCaseWidget(_BaseFrame):
    """Interactive drag-and-drop frame for medical imaging files and DICOM folders."""

    def __init__(self, on_file_loaded_callback=None, parent=None):
        super(DragDropCaseWidget, self).__init__(parent)
        self.on_file_loaded_callback = on_file_loaded_callback
        self.setAcceptDrops(True)
        self.setMinimumHeight(105)

        # Style with clean clinical border
        self.default_style = """
            QFrame {
                border: 2px dashed #3B82F6;
                border-radius: 10px;
                background-color: rgba(30, 41, 59, 0.5);
            }
        """
        self.hover_style = """
            QFrame {
                border: 2px dashed #10B981;
                border-radius: 10px;
                background-color: rgba(16, 185, 129, 0.2);
            }
        """
        self.setStyleSheet(self.default_style)

        layout = qt.QVBoxLayout(self)
        layout.setAlignment(qt.Qt.AlignCenter)

        self.icon_label = qt.QLabel("📂 Drag & Drop Medical Scan, DICOM Folder, or 3D Mesh Here")
        self.icon_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #38BDF8;")
        self.icon_label.setAlignment(qt.Qt.AlignCenter)
        layout.addWidget(self.icon_label)

        self.sub_label = qt.QLabel("Volumes: NIfTI, NRRD, DICOM, MHA  |  Meshes: VTK, STL, OBJ, PLY, VTP")
        self.sub_label.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.sub_label.setAlignment(qt.Qt.AlignCenter)
        layout.addWidget(self.sub_label)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self.hover_style)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.default_style)

    def dropEvent(self, event):
        self.setStyleSheet(self.default_style)
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if os.path.exists(file_path):
                if self.on_file_loaded_callback:
                    self.on_file_loaded_callback(file_path)


#
# Main Module Widget
#
class MyModuleWidget(ScriptedLoadableModuleWidget):
    """Qt GUI for SlicerFlow Copilot inside 3D Slicer."""

    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        self.logic = SlicerFlowLogic()
        self.active_case_path = ""
        self.active_metadata = None
        self.current_plan = None
        self.last_report_text = ""
        self.llm_client = ExternalLLMClient()

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        # Output directory
        self.output_dir = os.path.join(COPILOT_DIR, "outputs")
        os.makedirs(self.output_dir, exist_ok=True)

        # 1. HEADER SECTION
        header_card = qt.QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0F172A, stop:1 #1E293B);
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        header_layout = qt.QVBoxLayout(header_card)
        title_label = qt.QLabel("🧬 SlicerFlow Copilot")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #F8FAFC;")
        header_layout.addWidget(title_label)

        sub_label = qt.QLabel("From Natural Language to Verified & Reproducible 3D Slicer Workflows")
        sub_label.setStyleSheet("font-size: 11px; color: #38BDF8;")
        header_layout.addWidget(sub_label)

        tag_label = qt.QLabel("AI understands • Rules validate • Slicer executes • Humans approve")
        tag_label.setStyleSheet("font-size: 9px; color: #94A3B8; font-weight: bold; text-transform: uppercase;")
        header_layout.addWidget(tag_label)

        self.layout.addWidget(header_card)

        # 2. CASE INPUT & TECHNICAL ANALYSIS SECTION
        case_group = ctk.ctkCollapsibleButton()
        case_group.text = "1. Medical Case Input & Technical Analysis"
        self.layout.addWidget(case_group)
        case_layout = qt.QVBoxLayout(case_group)

        # Drop zone
        self.drop_widget = DragDropCaseWidget(on_file_loaded_callback=self.load_case_file)
        case_layout.addWidget(self.drop_widget)

        # File browse and reset buttons
        btn_layout = qt.QHBoxLayout()
        self.btn_browse_file = qt.QPushButton("📁 Browse Scan File")
        self.btn_browse_file.setToolTip("Open NIfTI (.nii, .nii.gz), NRRD (.nrrd), or DICOM file")
        self.btn_browse_file.connect("clicked()", self.on_browse_file)
        btn_layout.addWidget(self.btn_browse_file)

        self.btn_browse_folder = qt.QPushButton("📂 Browse DICOM Folder")
        self.btn_browse_folder.setToolTip("Select directory containing clinical DICOM slices")
        self.btn_browse_folder.connect("clicked()", self.on_browse_folder)
        btn_layout.addWidget(self.btn_browse_folder)

        self.btn_reset_scene = qt.QPushButton("↺ Reset Scene")
        self.btn_reset_scene.setToolTip("Clear Slicer scene and reset current workflow")
        self.btn_reset_scene.connect("clicked()", self.on_reset_scene)
        btn_layout.addWidget(self.btn_reset_scene)
        case_layout.addLayout(btn_layout)

        # Metadata display label
        self.meta_label = qt.QLabel("No case loaded yet. Drop a medical volume above or click Browse.")
        self.meta_label.setStyleSheet("""
            QLabel {
                background: #0B1120;
                border: 1px solid #1E293B;
                border-radius: 6px;
                padding: 8px;
                font-family: monospace;
                font-size: 11px;
                color: #38BDF8;
            }
        """)
        case_layout.addWidget(self.meta_label)

        # 3. DEDICATED CHAT-LIKE COPILOT AGENT SECTION
        chat_group = ctk.ctkCollapsibleButton()
        chat_group.text = "2. Dedicated SlicerFlow AI Chat Agent"
        self.layout.addWidget(chat_group)
        chat_layout = qt.QVBoxLayout(chat_group)

        # LLM Engine Selector
        mode_layout = qt.QHBoxLayout()
        mode_label = qt.QLabel("AI Engine:")
        mode_label.setStyleSheet("font-weight: bold; color: #F1F5F9;")
        mode_layout.addWidget(mode_label)

        self.engine_combo = qt.QComboBox()
        self.engine_combo.addItem("Google Gemini API (models/gemini-3.6-flash)")
        self.engine_combo.addItem("Google Gemini API (gemini-2.0-flash)")
        self.engine_combo.addItem("Offline Deterministic Rule Parser")
        mode_layout.addWidget(self.engine_combo)
        chat_layout.addLayout(mode_layout)

        # Chat message history
        self.chat_history = qt.QTextBrowser()
        self.chat_history.setMinimumHeight(240)
        self.chat_history.setStyleSheet("""
            QTextBrowser {
                background-color: #050811;
                border: 1px solid #1E293B;
                border-radius: 8px;
                padding: 10px;
                font-family: sans-serif;
                font-size: 12px;
                color: #F8FAFC;
            }
        """)
        chat_layout.addWidget(self.chat_history)

        self._append_agent_message(
            "Hello! I am your <b>SlicerFlow Copilot</b> powered by Google Gemini API.<br>"
            "Drop or browse a medical scan above and describe your workflow in natural language.<br>"
            "<i>Example: 'Prepare this CT scan, segment bone, and reconstruct a 3D surface model.'</i>"
        )

        # Quick Suggestion Chips
        chips_layout = qt.QHBoxLayout()
        chip_bone = qt.QPushButton("🦴 Reconstruct Bone")
        chip_bone.connect("clicked()", lambda: self._on_chip_clicked("Prepare this CT scan and reconstruct the bone 3D model"))
        chips_layout.addWidget(chip_bone)

        chip_airway = qt.QPushButton("🫁 Segment Airway")
        chip_airway.connect("clicked()", lambda: self._on_chip_clicked("Segment airway and trachea anatomy"))
        chips_layout.addWidget(chip_airway)

        chip_tissue = qt.QPushButton("🫀 Soft Tissue Prep")
        chip_tissue.connect("clicked()", lambda: self._on_chip_clicked("Prepare soft tissue window and segment organs"))
        chips_layout.addWidget(chip_tissue)

        chip_diag = qt.QPushButton("⚠️ Test Rejection")
        chip_diag.connect("clicked()", lambda: self._on_chip_clicked("Diagnose malignant tumor in this scan"))
        chips_layout.addWidget(chip_diag)
        chat_layout.addLayout(chips_layout)

        # Chat Input Field & Send Button
        input_layout = qt.QHBoxLayout()
        self.chat_input = qt.QLineEdit()
        self.chat_input.setPlaceholderText("Ask SlicerFlow in natural language...")
        self.chat_input.connect("returnPressed()", self.on_send_chat)
        input_layout.addWidget(self.chat_input)

        self.btn_send = qt.QPushButton("Send ➔")
        self.btn_send.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 6px 14px;")
        self.btn_send.connect("clicked()", self.on_send_chat)
        input_layout.addWidget(self.btn_send)
        chat_layout.addLayout(input_layout)

        # 4. WORKFLOW PLAN & APPROVAL GATE
        self.plan_group = ctk.ctkCollapsibleButton()
        self.plan_group.text = "3. Workflow Plan & Human Approval Gate"
        self.layout.addWidget(self.plan_group)
        plan_layout = qt.QVBoxLayout(self.plan_group)

        self.plan_summary_label = qt.QLabel("No workflow plan generated yet.")
        self.plan_summary_label.setStyleSheet("font-family: monospace; font-size: 11px; color: #CBD5E1;")
        plan_layout.addWidget(self.plan_summary_label)

        action_btn_layout = qt.QHBoxLayout()
        self.btn_approve_exec = qt.QPushButton("🚀 Approve & Execute in Slicer")
        self.btn_approve_exec.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 8px;")
        self.btn_approve_exec.setEnabled(False)
        self.btn_approve_exec.connect("clicked()", self.on_approve_and_execute)
        action_btn_layout.addWidget(self.btn_approve_exec)

        self.btn_view_script = qt.QPushButton("🔍 View Slicer Script")
        self.btn_view_script.setEnabled(False)
        self.btn_view_script.connect("clicked()", self.on_view_script)
        action_btn_layout.addWidget(self.btn_view_script)
        plan_layout.addLayout(action_btn_layout)

        # 3D Viewport Quick Camera Controls
        camera_box = qt.QGroupBox("3D Viewport Controls")
        camera_layout = qt.QHBoxLayout(camera_box)

        btn_cam_ant = qt.QPushButton("Anterior")
        btn_cam_ant.connect("clicked()", lambda: self.set_3d_view_camera("anterior"))
        camera_layout.addWidget(btn_cam_ant)

        btn_cam_post = qt.QPushButton("Posterior")
        btn_cam_post.connect("clicked()", lambda: self.set_3d_view_camera("posterior"))
        camera_layout.addWidget(btn_cam_post)

        btn_cam_lat = qt.QPushButton("Lateral")
        btn_cam_lat.connect("clicked()", lambda: self.set_3d_view_camera("lateral"))
        camera_layout.addWidget(btn_cam_lat)

        btn_cam_fit = qt.QPushButton("Fit 3D View")
        btn_cam_fit.connect("clicked()", lambda: self.set_3d_view_camera("reset"))
        camera_layout.addWidget(btn_cam_fit)

        plan_layout.addWidget(camera_box)

        # 5. OUTPUTS & PROVENANCE SECTION
        self.out_group = ctk.ctkCollapsibleButton()
        self.out_group.text = "4. Verified Outputs & Reproducibility Manifest"
        self.layout.addWidget(self.out_group)
        out_layout = qt.QVBoxLayout(self.out_group)

        self.out_status_label = qt.QLabel("Outputs will be listed here following execution.")
        self.out_status_label.setStyleSheet("font-size: 11px; color: #94A3B8;")
        out_layout.addWidget(self.out_status_label)

        out_btn_layout = qt.QHBoxLayout()
        self.btn_copy_report = qt.QPushButton("📋 Copy Report to Clipboard")
        self.btn_copy_report.setEnabled(False)
        self.btn_copy_report.connect("clicked()", self.on_copy_report)
        out_btn_layout.addWidget(self.btn_copy_report)

        self.btn_open_out_dir = qt.QPushButton("📂 Open Outputs Folder")
        self.btn_open_out_dir.connect("clicked()", self.open_output_folder)
        out_btn_layout.addWidget(self.btn_open_out_dir)
        out_layout.addLayout(out_btn_layout)

        # Spacer
        self.layout.addStretch(1)

    def _append_user_message(self, text: str):
        msg = f"""
        <div style="margin: 8px 0; text-align: right;">
            <span style="background-color: #1E3A8A; color: #F8FAFC; padding: 6px 12px; border-radius: 12px; display: inline-block;">
                <b>You:</b> {text}
            </span>
        </div>
        """
        self.chat_history.append(msg)

    def _append_agent_message(self, text: str, reasoning: str = ""):
        reasoning_html = ""
        if reasoning:
            reasoning_html = f"""
            <div style="background-color: #111827; border-left: 3px solid #F59E0B; padding: 6px 10px; margin: 4px 0; border-radius: 4px; font-size: 11px; color: #FCD34D;">
                <b>🧠 AI Radiologist Reasoning:</b><br>{reasoning}
            </div>
            """

        msg = f"""
        <div style="margin: 8px 0; text-align: left;">
            <div style="background-color: #1E293B; border: 1px solid #334155; color: #F1F5F9; padding: 8px 12px; border-radius: 12px;">
                <b style="color: #38BDF8;">SlicerFlow Copilot:</b><br>
                {reasoning_html}
                {text}
            </div>
        </div>
        """
        self.chat_history.append(msg)

    def _on_chip_clicked(self, prompt: str):
        self.chat_input.setText(prompt)
        self.on_send_chat()

    def on_browse_file(self):
        """Native file picker for medical scans."""
        file_path, _ = qt.QFileDialog.getOpenFileName(
            None,
            "Select Medical Scan Volume",
            "",
            "Medical Images (*.nrrd *.nii *.nii.gz *.dcm *.mha);;All Files (*)"
        )
        if file_path and os.path.exists(file_path):
            self.load_case_file(file_path)

    def on_browse_folder(self):
        """Native folder picker for DICOM directory."""
        folder_path = qt.QFileDialog.getExistingDirectory(
            None,
            "Select Clinical DICOM Directory"
        )
        if folder_path and os.path.exists(folder_path):
            self.load_case_file(folder_path)

    def on_reset_scene(self):
        """Clear Slicer scene and reset workflow state."""
        slicer.mrmlScene.Clear(0)
        self.active_case_path = ""
        self.active_metadata = None
        self.current_plan = None
        self.last_report_text = ""
        self.meta_label.setText("Scene cleared. Ready for new case input.")
        self.plan_summary_label.setText("No workflow plan generated yet.")
        self.btn_approve_exec.setEnabled(False)
        self.btn_view_script.setEnabled(False)
        self.btn_copy_report.setEnabled(False)
        self._append_agent_message("Scene and active workflow have been reset.")

    def set_3d_view_camera(self, orientation: str):
        """Sets the 3D camera orientation."""
        layout_manager = slicer.app.layoutManager()
        if not layout_manager:
            return
        three_d_view = layout_manager.threeDWidget(0).threeDView()
        if not three_d_view:
            return

        if orientation == "anterior":
            three_d_view.lookFromAxis(ctk.ctkAxes.Anterior)
        elif orientation == "posterior":
            three_d_view.lookFromAxis(ctk.ctkAxes.Posterior)
        elif orientation == "lateral":
            three_d_view.lookFromAxis(ctk.ctkAxes.Left)
        elif orientation == "reset":
            three_d_view.resetCamera()

    # Mesh/model file extensions recognized by SlicerFlow
    MODEL_EXTENSIONS = {".vtk", ".stl", ".obj", ".ply", ".vtp", ".vtu", ".g", ".byu", ".off"}
    # Volume file extensions
    VOLUME_EXTENSIONS = {".nrrd", ".nhdr", ".nii", ".nii.gz", ".mha", ".mhd", ".dcm", ".ima", ".gipl", ".hdr", ".img"}

    @staticmethod
    def _is_model_file(file_path):
        """Check if a single file is a 3D mesh/model."""
        ext = os.path.splitext(file_path.lower())[1]
        return ext in MyModuleWidget.MODEL_EXTENSIONS

    @staticmethod
    def _is_model_directory(dir_path):
        """Check if a directory contains 3D mesh/model files (e.g. MESHES_VTK)."""
        if not os.path.isdir(dir_path):
            return False, []
        model_files = []
        for f in os.listdir(dir_path):
            ext = os.path.splitext(f.lower())[1]
            if ext in MyModuleWidget.MODEL_EXTENSIONS:
                model_files.append(os.path.join(dir_path, f))
        return len(model_files) > 0, model_files

    @staticmethod
    def _is_dicom_directory(dir_path):
        """Check if a directory contains DICOM files."""
        if not os.path.isdir(dir_path):
            return False
        for f in os.listdir(dir_path):
            ext = os.path.splitext(f.lower())[1]
            if ext in (".dcm", ".ima"):
                return True
            # DICOM files sometimes have no extension — check first few
            if ext == "" and not f.startswith("."):
                try:
                    full = os.path.join(dir_path, f)
                    with open(full, "rb") as fh:
                        fh.seek(128)
                        if fh.read(4) == b"DICM":
                            return True
                except Exception:
                    pass
        return False

    def load_case_file(self, file_path: str):
        """Analyze case and load volume or 3D model into 3D Slicer MRML scene.

        Supports:
        - Volume files: NIfTI, NRRD, DICOM, MetaImage → slicer.util.loadVolume()
        - 3D mesh files: VTK, STL, OBJ, PLY, VTP → slicer.util.loadModel()
        - Directories of VTK meshes: loads all mesh files in the directory
        - DICOM directories: loads via DICOM series reader
        """
        self.active_case_path = file_path
        is_dir = os.path.isdir(file_path)

        # ------------------------------------------------------------------
        # CASE 1: Directory containing VTK/STL mesh files
        # ------------------------------------------------------------------
        if is_dir:
            is_mesh_dir, mesh_files = self._is_model_directory(file_path)
            if is_mesh_dir:
                self._load_model_directory(file_path, mesh_files)
                return
            # Otherwise fall through to volume/DICOM loading

        # ------------------------------------------------------------------
        # CASE 2: Single 3D mesh/model file
        # ------------------------------------------------------------------
        if not is_dir and self._is_model_file(file_path):
            self._load_single_model(file_path)
            return

        # ------------------------------------------------------------------
        # CASE 3: Volume files (NIfTI, NRRD, DICOM, MHA) — original behavior
        # ------------------------------------------------------------------
        self.active_metadata = CaseAnalyzer.analyze_case(file_path)
        meta = self.active_metadata
        dim_str = f"{meta.dimensions[0]}×{meta.dimensions[1]}×{meta.dimensions[2]}" if meta.dimensions else "N/A"
        spc_str = f"{meta.spacing[0]:.2f}×{meta.spacing[1]:.2f}×{meta.spacing[2]:.2f} mm" if meta.spacing else "N/A"
        hu_str = f"[{meta.intensity_min:.0f}, {meta.intensity_max:.0f}] HU" if meta.intensity_min is not None else "N/A"

        self.meta_label.setText(
            f"File/Dir: {meta.file_name}\n"
            f"Format: {meta.file_format} | Modality: {meta.modality}\n"
            f"Dimensions: {dim_str} | Spacing: {spc_str}\n"
            f"HU Range: {hu_str} | Status: {meta.status}"
        )

        try:
            vol_node = slicer.util.loadVolume(file_path)
            if vol_node:
                slicer.util.resetSliceViews()
                self._append_agent_message(
                    f"Loaded <b>{meta.file_name}</b> ({meta.file_format}, {meta.modality}) into Slicer MRML scene.<br>"
                    f"Dimensions: {dim_str}, Spacing: {spc_str}. Ready for commands!"
                )
        except Exception as e:
            self._append_agent_message(
                f"<span style='color: #EF4444;'><b>Load Error</b></span><br>"
                f"Could not load <b>{os.path.basename(file_path)}</b> as a volume: {str(e)}<br>"
                f"<span style='color: #94A3B8;'>If this is a 3D mesh file, try dropping individual .vtk/.stl/.obj files.</span>"
            )

    def _load_single_model(self, file_path):
        """Load a single 3D mesh/model file into Slicer."""
        fname = os.path.basename(file_path)
        ext = os.path.splitext(fname)[1].lower()

        self.meta_label.setText(
            f"File: {fname}\n"
            f"Format: 3D Model ({ext.upper()}) | Type: Surface Mesh\n"
            f"Status: Loading..."
        )

        try:
            model_node = slicer.util.loadModel(file_path)
            if model_node:
                # Get mesh statistics
                pd = model_node.GetPolyData()
                n_points = pd.GetNumberOfPoints() if pd else 0
                n_cells = pd.GetNumberOfCells() if pd else 0

                self.meta_label.setText(
                    f"File: {fname}\n"
                    f"Format: 3D Model ({ext.upper()}) | Type: Surface Mesh\n"
                    f"Vertices: {n_points:,} | Faces: {n_cells:,}\n"
                    f"Status: LOADED"
                )

                # Reset 3D view to show the model
                try:
                    lm = slicer.app.layoutManager()
                    if lm:
                        w3d = lm.threeDWidget(0)
                        if w3d:
                            w3d.threeDView().resetCamera()
                except Exception:
                    pass

                self._append_agent_message(
                    f"Loaded 3D model <b>{fname}</b> into Slicer 3D view.<br>"
                    f"Vertices: {n_points:,} | Faces: {n_cells:,}"
                )
        except Exception as e:
            self.meta_label.setText(f"File: {fname}\nStatus: LOAD FAILED\nError: {str(e)}")
            self._append_agent_message(
                f"<span style='color: #EF4444;'>Failed to load model {fname}: {str(e)}</span>"
            )

    def _load_model_directory(self, dir_path, model_files):
        """Load all 3D mesh/model files from a directory into Slicer."""
        dir_name = os.path.basename(dir_path)
        total = len(model_files)
        loaded = 0
        total_verts = 0
        total_faces = 0

        self.meta_label.setText(
            f"Directory: {dir_name}\n"
            f"Format: 3D Mesh Directory | Files: {total}\n"
            f"Status: Loading..."
        )

        for mf in sorted(model_files):
            try:
                model_node = slicer.util.loadModel(mf)
                if model_node:
                    pd = model_node.GetPolyData()
                    if pd:
                        total_verts += pd.GetNumberOfPoints()
                        total_faces += pd.GetNumberOfCells()
                    loaded += 1
            except Exception as e:
                logging.warning(f"Failed to load mesh {mf}: {e}")

        # Reset 3D view camera
        try:
            lm = slicer.app.layoutManager()
            if lm:
                w3d = lm.threeDWidget(0)
                if w3d:
                    w3d.threeDView().resetCamera()
        except Exception:
            pass

        file_names = [os.path.basename(f) for f in sorted(model_files)]
        names_str = ", ".join(file_names[:6])
        if len(file_names) > 6:
            names_str += f" ... (+{len(file_names) - 6} more)"

        self.meta_label.setText(
            f"Directory: {dir_name}\n"
            f"Format: 3D Mesh Directory | Loaded: {loaded}/{total} models\n"
            f"Total Vertices: {total_verts:,} | Total Faces: {total_faces:,}\n"
            f"Status: LOADED"
        )

        self._append_agent_message(
            f"Loaded <b>{loaded}/{total}</b> 3D models from <b>{dir_name}/</b> into Slicer 3D view.<br>"
            f"Models: {names_str}<br>"
            f"Total Vertices: {total_verts:,} | Total Faces: {total_faces:,}"
        )

    def on_send_chat(self):
        text = self.chat_input.text.strip()
        if not text:
            return

        self.chat_input.clear()
        self._append_user_message(text)

        # Engine selection
        idx = self.engine_combo.currentIndex
        meta_dict = self.active_metadata.to_dict() if self.active_metadata else None

        if idx == 0:  # Gemini 3.6 Flash
            self.llm_client.model_name = os.getenv("LLM_MODEL", "models/gemini-3.6-flash")
            intent = self.llm_client.parse_workflow(text, case_metadata=meta_dict)
        elif idx == 1:  # Gemini 2.0 Flash
            self.llm_client.model_name = "gemini-2.0-flash"
            intent = self.llm_client.parse_workflow(text, case_metadata=meta_dict)
        else:  # Offline rule parser
            intent = RuleBasedParser.parse(text, context=meta_dict)

        if not intent.is_supported:
            self._append_agent_message(
                f"<span style='color: #EF4444;'><b>Unsupported Request Blocked</b></span><br>"
                f"<pre style='color: #FCA5A5;'>{intent.unsupported_reason}</pre>",
                reasoning=intent.reasoning
            )
            self.btn_approve_exec.setEnabled(False)
            self.btn_view_script.setEnabled(False)
            return

        # Handle general conversation & Q&A queries naturally without generating a workflow plan
        if intent.intent in ("general_conversation", "qa", "general_query") or not intent.operations:
            self._append_agent_message(
                f"<b>SlicerFlow Copilot</b>:<br>{intent.explanation}",
                reasoning=intent.reasoning
            )
            return

        # Build workflow plan
        planner = WorkflowPlanner()
        case_id = os.path.splitext(os.path.basename(self.active_case_path))[0] if self.active_case_path else "CASE_001"
        plan = planner.plan(
            intent=intent,
            case_id=case_id,
            case_file_path=self.active_case_path
        )
        self.current_plan = plan

        # Pre-execution validation
        is_valid, messages, _ = CommandValidator.validate_plan(plan, file_path=self.active_case_path)

        steps_html = "<ol style='margin: 4px 0; padding-left: 20px;'>"
        for s in plan.steps:
            steps_html += f"<li><b>{s.display_name}</b> (<code>{s.operation}</code>)</li>"
        steps_html += "</ol>"

        validation_status = (
            "<span style='color: #34D399;'><b>✓ READY FOR EXECUTION</b> (All rules verified)</span>"
            if is_valid
            else f"<span style='color: #EF4444;'><b>✗ BLOCKED</b>: {'; '.join(messages)}</span>"
        )

        response_html = f"""
        I translated your request into a verified workflow plan:<br>
        <b>Intent</b>: <code>{intent.intent}</code> | <b>Target Anatomy</b>: <code>{intent.parameters.get('target_anatomy', 'bone')}</code><br>
        {steps_html}
        <b>Validation Status</b>: {validation_status}<br><br>
        <i>Click <b>Approve & Execute</b> below to run the automation directly in 3D Slicer.</i>
        """
        self._append_agent_message(response_html, reasoning=intent.reasoning)

        # Update Workflow Plan Section
        self.plan_summary_label.setText(
            f"Plan ID: {plan.plan_id}\n"
            f"Operations: {' -> '.join(plan.operations_list())}\n"
            f"Status: {'VALIDATED' if is_valid else 'BLOCKED'}"
        )

        self.btn_approve_exec.setEnabled(is_valid)
        self.btn_view_script.setEnabled(True)

    def on_view_script(self):
        if not self.current_plan:
            return
        script_code = SlicerCodeGenerator.generate_slicer_script(
            plan=self.current_plan,
            input_file_path=self.active_case_path,
            output_dir=self.output_dir
        )
        msg_box = qt.QMessageBox()
        msg_box.setWindowTitle("Generated 3D Slicer Python Automation Script")
        msg_box.setText(script_code)
        msg_box.exec_()

    def on_approve_and_execute(self):
        if not self.current_plan:
            return

        self._append_agent_message("🚀 <b>Execution approved!</b> Running automated 3D Slicer pipeline...")

        def log_cb(msg):
            self._append_agent_message(f"<span style='color: #94A3B8;'>{msg}</span>")

        success, outputs = self.logic.execute_workflow_in_slicer(
            plan=self.current_plan,
            input_file=self.active_case_path,
            output_dir=self.output_dir,
            log_callback=log_cb
        )

        if success:
            stl_path = outputs.get("3d_model_stl", "")
            manifest_path = outputs.get("reproducibility_manifest", "")
            report_path = outputs.get("case_report", "")

            # Read report for clipboard
            if report_path and os.path.exists(report_path):
                with open(report_path, "r", encoding="utf-8") as rf:
                    self.last_report_text = rf.read()
                self.btn_copy_report.setEnabled(True)

            self._append_agent_message(
                f"<span style='color: #34D399;'><b>🎉 Workflow Completed Successfully!</b></span><br>"
                f"• 3D Surface Model displayed in 3D View and saved to: <code>{os.path.basename(stl_path)}</code><br>"
                f"• Provenance Manifest created: <code>{os.path.basename(manifest_path)}</code><br>"
                f"• Case Processing Report created: <code>{os.path.basename(report_path)}</code>"
            )

            self.out_status_label.setText(
                f"✓ 3D Model: {stl_path}\n"
                f"✓ Manifest: {manifest_path}\n"
                f"✓ Report: {report_path}"
            )
        else:
            self._append_agent_message("<span style='color: #EF4444;'><b>Execution failed.</b> Check logs.</span>")

    def on_copy_report(self):
        if self.last_report_text:
            qt.QApplication.clipboard().setText(self.last_report_text)
            self._append_agent_message("<span style='color: #38BDF8;'>✓ Audit report copied to clipboard!</span>")

    def open_output_folder(self):
        if os.path.exists(self.output_dir):
            qt.QDesktopServices.openUrl(qt.QUrl.fromLocalFile(self.output_dir))


#
# SlicerFlow Logic Class (Manipulates active Slicer scene)
#
class SlicerFlowLogic(ScriptedLoadableModuleLogic):
    """Executes validated workflows directly on Slicer MRML Scene."""

    def execute_workflow_in_slicer(self, plan: WorkflowPlan, input_file: str, output_dir: str, log_callback=None):
        outputs = {}
        try:
            # 1. Volume
            if log_callback:
                log_callback("Loading volume into MRML scene...")
            vol_node = slicer.util.loadVolume(input_file)
            if not vol_node:
                return False, {}
            slicer.util.resetSliceViews()

            # 2. Extract parameters
            seg_step = plan.get_step("segment")
            anatomy = seg_step.parameters.get("target_anatomy", "bone") if seg_step else "bone"
            lower_th = float(seg_step.parameters.get("lower_threshold", 250.0)) if seg_step else 250.0
            upper_th = float(seg_step.parameters.get("upper_threshold", 2000.0)) if seg_step else 2000.0

            # 3. Create Segmentation Node
            if log_callback:
                log_callback(f"Applying threshold segmentation for {anatomy} ([{lower_th:.0f}, {upper_th:.0f}] HU)...")

            seg_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", f"SlicerFlow_{anatomy.title()}")
            seg_node.CreateDefaultDisplayNodes()
            seg_node.SetReferenceImageGeometryParameterFromVolumeNode(vol_node)

            segment_id = seg_node.GetSegmentation().AddEmptySegment(anatomy)

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

            slicer.mrmlScene.RemoveNode(editor_node)

            # 4. Generate 3D Representation
            if log_callback:
                log_callback("Reconstructing 3D surface mesh in Slicer 3D View...")

            seg_node.CreateClosedSurfaceRepresentation()

            # Reset 3D camera
            layout_manager = slicer.app.layoutManager()
            if layout_manager:
                three_d_view = layout_manager.threeDWidget(0).threeDView()
                if three_d_view:
                    three_d_view.resetCamera()

            # 5. Export STL
            stl_path = os.path.join(output_dir, f"{plan.case_id}_{anatomy}.stl")
            slicer.modules.segmentations.logic().ExportSegmentsClosedSurfaceRepresentationToFiles(
                output_dir,
                seg_node,
                None,
                "STL"
            )
            outputs["3d_model_stl"] = stl_path

            # 6. Provenance Manifest & Report
            manifest_data = ManifestGenerator.generate_manifest(
                plan=plan,
                input_file=input_file,
                output_files=outputs
            )
            manifest_path = os.path.join(output_dir, f"{plan.case_id}_manifest.json")
            ManifestGenerator.save_manifest(manifest_data, manifest_path)
            outputs["reproducibility_manifest"] = manifest_path

            report_md = ReportGenerator.generate_markdown_report(
                plan=plan,
                input_file=input_file,
                output_files=outputs
            )
            report_path = os.path.join(output_dir, f"{plan.case_id}_processing_report.md")
            ReportGenerator.save_report(report_md, report_path)
            outputs["case_report"] = report_path

            return True, outputs

        except Exception as e:
            logging.error(f"Execution in Slicer failed: {str(e)}")
            return False, {}
