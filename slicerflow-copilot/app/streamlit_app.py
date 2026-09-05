"""SlicerFlow Copilot - Streamlit Web Application.

From Natural Language to Verified and Reproducible 3D Medical Imaging Workflows.
Combines N34 (Automated Case Preparation) and N35 (AI-assisted Slicer Automation).
"""

import os
import sys
import time
import json
from pathlib import Path
import streamlit as st
import numpy as np
from dotenv import load_dotenv

# Load .env from project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

# Ensure root package is in python path
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core.operation_registry import (
    get_supported_operations,
    get_unsupported_operation_message,
    SUPPORTED_OPERATIONS,
)
from core.workflow import WorkflowPlan, WorkflowStep, OperationStatus
from core.orchestrator import PipelineOrchestrator
from copilot.parser import RuleBasedParser
from copilot.planner import WorkflowPlanner
from copilot.llm_client import ExternalLLMClient
from analyzer.case_analyzer import CaseAnalyzer
from analyzer.metadata import CaseMetadata
from automation.volume import VolumeProcessor
from automation.code_generator import SlicerCodeGenerator
from automation.slicer_interface import SlicerInterface
from automation.console_bridge import ConsoleBridge
from validation.command_validator import CommandValidator
from reporting.manifest import ManifestGenerator
from reporting.report import ReportGenerator

# Page configuration
st.set_page_config(
    page_title="SlicerFlow Copilot",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load CSS
CSS_FILE = os.path.join(ROOT_DIR, "app", "styles.css")
if os.path.exists(CSS_FILE):
    with open(CSS_FILE, "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# App Data Directories
SAMPLE_DIR = os.path.join(ROOT_DIR, "data", "sample")
OUTPUTS_DIR = os.path.join(ROOT_DIR, "outputs")
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# Initialize Session State
if "case_file" not in st.session_state:
    sample_spine = os.path.join(SAMPLE_DIR, "sample_spine_ct.nrrd")
    st.session_state.case_file = sample_spine if os.path.exists(sample_spine) else ""

if "case_metadata" not in st.session_state:
    st.session_state.case_metadata = None

if "workflow_plan" not in st.session_state:
    st.session_state.workflow_plan = None

if "executed_plan" not in st.session_state:
    st.session_state.executed_plan = None

if "console_logs" not in st.session_state:
    st.session_state.console_logs = []

if "window_preset" not in st.session_state:
    st.session_state.window_preset = "bone"


# ------------------------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🧬 SlicerFlow Copilot")
    st.markdown("Automated 3D Slicer Case Preparation Pipeline & Natural Language Copilot")
    st.markdown("---")

    # Slicer Environment Status
    slicer_bridge = SlicerInterface()
    slicer_status = slicer_bridge.get_status()
    st.markdown("#### ⚙️ 3D Slicer Environment")
    if slicer_status["is_available"]:
        st.success(f"✓ 3D Slicer Detected (`v{slicer_status['version']}`)")
        st.caption(f"Path: `{slicer_status['slicer_executable'] or slicer_status['python_slicer_executable']}`")
    else:
        st.info("ℹ️ Slicer binary not found in standard paths. Operating in Embedded Medical Imaging Engine mode.")

    st.markdown("---")
    st.markdown("#### 🤖 Copilot Intelligence Engine")
    llm_mode = st.radio(
        "Parser Mode:",
        ["Google Gemini API (models/gemini-3.6-flash)", "Rule-Based (Offline / Instant)"],
        index=0
    )

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
    model_name = "models/gemini-3.6-flash"

    if "Gemini" in llm_mode:
        api_key = st.text_input("Gemini API Key:", value=api_key, type="password", placeholder="AQ.Ab...", help="Google Gemini API Key")
        base_url = st.text_input("Base URL:", value="https://generativelanguage.googleapis.com/v1beta/openai")
        model_name = st.text_input("Model Name:", value="models/gemini-3.6-flash")
        st.caption("Auto-falls back to deterministic parser if API fails or is offline.")

    st.markdown("---")
    st.markdown("#### 📋 Whitelisted Operations")
    for op in get_supported_operations():
        st.markdown(f"• `{op}`")

    st.markdown("---")
    st.markdown(
        "<div style='font-size: 11px; color: #94A3B8;'>"
        "<strong>Safety Notice:</strong> Research & workflow automation prototype. "
        "Does not provide diagnosis or autonomous medical decisions."
        "</div>",
        unsafe_allow_html=True
    )


# ------------------------------------------------------------------------------
# HEADER BANNER
# ------------------------------------------------------------------------------
st.markdown("""
<div class="main-header">
    <div class="main-title">
        <span>🧬 SlicerFlow Copilot</span>
    </div>
    <div class="main-subtitle">
        From Natural Language to Verified and Reproducible 3D Medical Imaging Workflows
    </div>
    <div class="safety-badge">
        AI UNDERSTANDS • RULES VALIDATE • 3D SLICER EXECUTES • VERIFICATION CHECKS • HUMANS APPROVE
    </div>
</div>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------------------
# SECTION 1: CASE INPUT
# ------------------------------------------------------------------------------
st.markdown("### 1. Medical Imaging Case Selection")

col_in1, col_in2 = st.columns([1.5, 2.5])

with col_in1:
    st.markdown("**Option A: Select Demo Dataset**")
    available_samples = []
    if os.path.exists(SAMPLE_DIR):
        available_samples = [f for f in os.listdir(SAMPLE_DIR) if f.endswith((".nrrd", ".nii.gz", ".nii"))]

    selected_sample = st.selectbox(
        "Built-in Benchmark Volumes:",
        available_samples if available_samples else ["No samples found"],
        index=0 if available_samples else 0
    )

    if st.button("Load Selected Dataset", use_container_width=True):
        if selected_sample and selected_sample != "No samples found":
            st.session_state.case_file = os.path.join(SAMPLE_DIR, selected_sample)
            st.session_state.case_metadata = None
            st.session_state.executed_plan = None
            st.rerun()

with col_in2:
    st.markdown("**Option B: Upload Medical Volume**")
    uploaded_file = st.file_uploader(
        "Drag & drop NIfTI (.nii, .nii.gz) or NRRD (.nrrd) scan:",
        type=["nii", "gz", "nrrd"],
        help="Volume will be saved to temporary case cache."
    )
    if uploaded_file is not None:
        save_path = os.path.join(OUTPUTS_DIR, uploaded_file.name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.session_state.case_file = save_path
        st.session_state.case_metadata = None
        st.session_state.executed_plan = None
        st.success(f"Loaded: {uploaded_file.name}")


# ------------------------------------------------------------------------------
# SECTION 2: CASE ANALYSIS
# ------------------------------------------------------------------------------
st.markdown("---")
st.markdown("### 2. Case Technical Analysis & Inspection")

current_case_file = st.session_state.case_file

if current_case_file and os.path.exists(current_case_file):
    if st.session_state.case_metadata is None:
        with st.spinner("Analyzing volume metadata and spatial geometry..."):
            st.session_state.case_metadata = CaseAnalyzer.analyze_case(current_case_file)

    meta: CaseMetadata = st.session_state.case_metadata

    col_meta, col_viewer = st.columns([1.5, 2.5])

    with col_meta:
        st.markdown(f"**File Name**: `{meta.file_name}`")
        st.markdown(f"**Format**: `{meta.file_format}` | **Modality**: `{meta.modality}`")

        # Metric badges
        dim_str = f"{meta.dimensions[0]} × {meta.dimensions[1]} × {meta.dimensions[2]}" if meta.dimensions else "Unavailable"
        spc_str = f"{meta.spacing[0]:.2f} × {meta.spacing[1]:.2f} × {meta.spacing[2]:.2f} mm" if meta.spacing else "Unavailable"
        hu_str = f"[{meta.intensity_min:.0f}, {meta.intensity_max:.0f}] HU" if meta.intensity_min is not None else "Unavailable"

        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-box">
                <div class="metric-label">Dimensions</div>
                <div class="metric-value">{dim_str}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Voxel Spacing</div>
                <div class="metric-value">{spc_str}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">HU Range</div>
                <div class="metric-value">{hu_str}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Integrity Status</div>
                <div class="metric-value" style="color: {'#34D399' if meta.status == 'VALID' else '#EF4444'};">{meta.status}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if meta.status != "VALID":
            st.error(f"Integrity warning: {meta.error_message}")

    with col_viewer:
        st.markdown("**2D Orthogonal Slice Inspection**")
        try:
            arr, spc, ori = VolumeProcessor.load_volume(current_case_file)
            nz, ny, nx = arr.shape

            c_win, c_slice = st.columns([1, 2])
            with c_win:
                window_choice = st.selectbox("CT Window:", ["Bone", "Soft_Tissue", "Lung"], index=0)
            with c_slice:
                axial_pos = st.slider("Axial Slice (Z):", 0, nz - 1, nz // 2)

            slices = VolumeProcessor.get_orthogonal_slices(arr, axial_idx=axial_pos, preset=window_choice.lower())

            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.caption(f"Axial (Slice {axial_pos}/{nz})")
                st.image(slices["axial"], use_container_width=True, clamp=True)
            with col_s2:
                st.caption(f"Coronal (Center Y={ny//2})")
                st.image(slices["coronal"], use_container_width=True, clamp=True)
            with col_s3:
                st.caption(f"Sagittal (Center X={nx//2})")
                st.image(slices["sagittal"], use_container_width=True, clamp=True)
        except Exception as e:
            st.warning(f"Could not render 2D slices: {str(e)}")
else:
    st.info("Please select or upload a case file above to initiate technical analysis.")


# ------------------------------------------------------------------------------
# SECTION 3: NATURAL LANGUAGE COPILOT
# ------------------------------------------------------------------------------
st.markdown("---")
st.markdown("### 3. SlicerFlow Natural Language Copilot")

example_queries = [
    "Prepare this CT scan and generate a 3D model of the selected anatomy.",
    "Inspect the case and reconstruct a 3D bone mesh.",
    "Segment the airway structure and export STL model.",
    "Diagnose malignant tumor in this scan (Safety Rejection Test)",
]

col_q1, col_q2, col_q3, col_q4 = st.columns(4)
query_text = ""

if col_q1.button("🦴 Prepare & 3D Model", use_container_width=True):
    st.session_state.current_query = example_queries[0]
if col_q2.button("🦴 Reconstruct Bone Mesh", use_container_width=True):
    st.session_state.current_query = example_queries[1]
if col_q3.button("🫁 Segment Airway", use_container_width=True):
    st.session_state.current_query = example_queries[2]
if col_q4.button("⚠️ Test Diagnosis Safety", use_container_width=True):
    st.session_state.current_query = example_queries[3]

default_q = st.session_state.get("current_query", example_queries[0])
user_prompt = st.text_input("Enter natural language request for 3D Slicer automation:", value=default_q)

btn_parse = st.button("Generate Workflow Plan", type="primary")

if btn_parse:
    with st.spinner("Translating natural language into validated structured workflow..."):
        if "Gemini" in llm_mode and api_key:
            client = ExternalLLMClient(api_key=api_key, base_url=base_url, model_name=model_name)
            meta_dict = st.session_state.case_metadata.to_dict() if st.session_state.case_metadata else None
            intent = client.parse_workflow(user_prompt, case_metadata=meta_dict)
        else:
            intent = RuleBasedParser.parse(user_prompt)

        planner = WorkflowPlanner()
        plan = planner.plan(
            intent=intent,
            case_id="CASE_HACKATHON_001",
            case_file_path=current_case_file
        )
        st.session_state.workflow_plan = plan
        st.session_state.parsed_intent = intent


# ------------------------------------------------------------------------------
# SECTION 4 & 5: WORKFLOW PLAN & COMMAND VALIDATION
# ------------------------------------------------------------------------------
plan: WorkflowPlan = st.session_state.workflow_plan
intent = st.session_state.get("parsed_intent")

if plan is not None:
    st.markdown("---")
    col_plan, col_val = st.columns([1.5, 1.5])

    with col_plan:
        st.markdown("### 4. Proposed Workflow Plan")
        if not intent.is_supported:
            st.error("🚫 **Unsupported Request Rejected**")
            st.markdown(f"```text\n{intent.unsupported_reason}\n```")
        else:
            st.markdown(f"**Intent**: `{intent.intent}` | **Target**: `{intent.parameters.get('target_anatomy', 'bone')}`")
            st.caption(intent.explanation)

            for i, step in enumerate(plan.steps):
                st.markdown(f"**{i+1}. {step.display_name}** (`{step.operation}`)")

    with col_val:
        st.markdown("### 5. Pre-Execution Validation Checks")
        is_valid, val_messages, step_statuses = CommandValidator.validate_plan(plan, file_path=current_case_file)

        if is_valid:
            st.success("✅ **READY FOR EXECUTION**")
            st.markdown("""
            - ✓ All requested commands exist in supported registry
            - ✓ Dependency execution order is strictly monotonic
            - ✓ Validated medical volume input is accessible
            - ✓ Technical dependencies verified
            """)
        else:
            st.error("❌ **WORKFLOW BLOCKED**")
            for msg in val_messages:
                st.markdown(f"• **Reason**: {msg}")

    # Inspect Slicer Python Script Expander
    with st.expander("🔍 Inspect Generated 3D Slicer Python Automation Script"):
        slicer_code = SlicerCodeGenerator.generate_slicer_script(
            plan=plan,
            input_file_path=current_case_file,
            output_dir=OUTPUTS_DIR
        )
        st.code(slicer_code, language="python")
        st.caption("Adheres to principle: AI understands -> Rules validate -> Slicer executes.")


# ------------------------------------------------------------------------------
# SECTION 6: EXECUTION PROGRESS & LIVE PYTHON / SLICER CONSOLE
# ------------------------------------------------------------------------------
st.markdown("---")
st.markdown("### 6. Pipeline Execution & Verification Engine")

col_exec_btn, col_exec_stats = st.columns([1, 3])
with col_exec_btn:
    can_execute = plan is not None and plan.is_validated and intent.is_supported
    run_btn = st.button("🚀 EXECUTE WORKFLOW", type="primary", disabled=not can_execute, use_container_width=True)

stepper_placeholder = st.empty()
console_placeholder = st.empty()


def render_stepper(current_plan: WorkflowPlan):
    status_icons = {
        OperationStatus.PENDING: ("○", "#94A3B8"),
        OperationStatus.RUNNING: ("⏳", "#38BDF8"),
        OperationStatus.SUCCESS: ("✅", "#34D399"),
        OperationStatus.WARNING: ("⚠", "#F59E0B"),
        OperationStatus.FAILED: ("❌", "#EF4444"),
        OperationStatus.BLOCKED: ("⊘", "#64748B"),
    }

    cols = stepper_placeholder.columns(len(current_plan.steps))
    for idx, (c, step) in enumerate(zip(cols, current_plan.steps)):
        icon, color = status_icons.get(step.status, ("•", "#FFF"))
        with c:
            st.markdown(
                f"<div style='text-align: center; border: 1px solid {color}; border-radius: 8px; padding: 8px; background: rgba(30, 41, 59, 0.5);'>"
                f"<div style='font-size: 20px;'>{icon}</div>"
                f"<div style='font-size: 11px; font-weight: 600; color: #F1F5F9; margin-top: 4px;'>{step.display_name}</div>"
                f"<div style='font-size: 10px; color: {color};'>{step.status.value}</div>"
                f"</div>",
                unsafe_allow_html=True
            )


if plan is not None and not run_btn and st.session_state.executed_plan is None:
    render_stepper(plan)

if run_btn and plan is not None:
    bridge = ConsoleBridge()
    orchestrator = PipelineOrchestrator(console_bridge=bridge)
    log_messages = []

    def log_cb(msg):
        log_messages.append(msg)
        console_placeholder.markdown(
            f"<div class='terminal-box'>"
            + "".join([f"<div class='terminal-line'>{line}</div>" for line in log_messages[-12:]])
            + "</div>",
            unsafe_allow_html=True
        )

    def step_cb(step, idx, total):
        render_stepper(plan)
        time.sleep(0.3)  # Visually smooth stepper transitions for demo

    with st.spinner("Executing verified Slicer workflow..."):
        executed = orchestrator.execute(
            plan=plan,
            file_path=current_case_file,
            output_dir=OUTPUTS_DIR,
            step_callback=step_cb,
            console_callback=log_cb
        )
        st.session_state.executed_plan = executed
        st.session_state.console_logs = log_messages
        render_stepper(executed)


# ------------------------------------------------------------------------------
# SECTION 7: FINAL RESULTS & 3D VIEWER
# ------------------------------------------------------------------------------
exec_plan: WorkflowPlan = st.session_state.executed_plan

if exec_plan is not None and exec_plan.final_status in (OperationStatus.SUCCESS, OperationStatus.WARNING):
    st.markdown("---")
    st.markdown("### 7. Final Results & Interactive 3D Model")

    st.success(f"🎉 **Workflow Execution Completed** — Status: `{exec_plan.final_status.value}`")

    ctx = getattr(exec_plan, "context", {})
    output_files = ctx.get("output_files", {})
    mesh_fig = ctx.get("mesh_figure")

    col_3d, col_artifacts = st.columns([2.5, 1.5])

    with col_3d:
        st.markdown("**Interactive 3D Anatomical Reconstruction**")
        if mesh_fig is not None:
            st.plotly_chart(mesh_fig, use_container_width=True)
        else:
            st.info("3D surface mesh was exported.")

    with col_artifacts:
        st.markdown("**Deliverables & Downloads**")

        # 3D Model download
        stl_path = output_files.get("3d_model_stl")
        if stl_path and os.path.exists(stl_path):
            with open(stl_path, "rb") as f:
                st.download_button(
                    label="📦 Download 3D Model (.STL)",
                    data=f.read(),
                    file_name=os.path.basename(stl_path),
                    mime="application/sla",
                    use_container_width=True
                )

        # Manifest download
        manifest_path = output_files.get("reproducibility_manifest")
        if manifest_path and os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                manifest_content = f.read()
            st.download_button(
                label="📜 Download Provenance Manifest (.JSON)",
                data=manifest_content,
                file_name=os.path.basename(manifest_path),
                mime="application/json",
                use_container_width=True
            )

        # Processing report download
        report_path = output_files.get("case_report")
        if report_path and os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                report_content = f.read()
            st.download_button(
                label="📄 Download Processing Report (.MD)",
                data=report_content,
                file_name=os.path.basename(report_path),
                mime="text/markdown",
                use_container_width=True
            )

        st.markdown("---")
        st.markdown("**Provenance Checksum**")
        if manifest_path and os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                mf = json.load(f)
            st.caption(f"Input SHA256: `{mf['input'].get('sha256', 'N/A')[:24]}...`")
            st.caption(f"Case ID: `{mf.get('case_id')}` | Plan ID: `{mf.get('plan_id')}`")

    # Tabs for Report and Manifest Inspections
    tab_report, tab_manifest, tab_console = st.tabs(["📄 Case Processing Report", "📜 Reproducibility Manifest (JSON)", "💻 Console Logs"])

    with tab_report:
        if report_path and os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                st.markdown(f.read())

    with tab_manifest:
        if manifest_path and os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                st.json(json.load(f))

    with tab_console:
        logs = st.session_state.console_logs
        st.markdown(
            f"<div class='terminal-box'>"
            + "".join([f"<div class='terminal-line'>{line}</div>" for line in logs])
            + "</div>",
            unsafe_allow_html=True
        )


# ------------------------------------------------------------------------------
# FOOTER
# ------------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    "<div style='text-align: center; font-size: 12px; color: #64748B; padding: 16px;'>"
    "SlicerFlow Copilot Hackathon MVP • Built for N34 & N35 • "
    "<strong>AI understands. Rules validate. 3D Slicer executes. Verification checks. Humans approve.</strong><br>"
    "Research prototype only. Not for clinical diagnosis or autonomous patient treatment."
    "</div>",
    unsafe_allow_html=True
)
