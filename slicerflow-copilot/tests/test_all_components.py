"""Comprehensive test suite for SlicerFlow Copilot.

Tests:
- test_supported_command()
- test_unsupported_command()
- test_copilot_parser_supported()
- test_workflow_validation()
- test_invalid_operation_order()
- test_case_validation()
- test_validators()
- test_manifest_generation()
- test_report_generation()
- test_llm_client_fallback()
- test_slicer_code_generation()
- test_end_to_end_orchestration()
"""

import os
import sys
import tempfile
import json
import pytest
import numpy as np
import SimpleITK as sitk

# Ensure slicerflow-copilot is on path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.operation_registry import is_supported_operation, get_supported_operations, get_unsupported_operation_message
from core.workflow import WorkflowPlan, WorkflowStep, OperationStatus
from core.orchestrator import PipelineOrchestrator
from copilot.parser import RuleBasedParser
from copilot.planner import WorkflowPlanner
from copilot.llm_client import ExternalLLMClient
from analyzer.case_analyzer import CaseAnalyzer
from validation.command_validator import CommandValidator
from validation.volume_validator import VolumeValidator
from validation.segmentation_validator import SegmentationValidator
from validation.output_validator import OutputValidator
from automation.code_generator import SlicerCodeGenerator
from reporting.manifest import ManifestGenerator
from reporting.report import ReportGenerator


@pytest.fixture
def sample_ct_path(tmp_path):
    """Generates a temporary, self-contained CT scan volume for testing (no static demo data)."""
    # Create (32, 64, 64) volume in Z, Y, X
    arr = np.zeros((32, 64, 64), dtype=np.int16) - 1000  # Air background (-1000 HU)
    # Soft tissue region
    arr[4:28, 10:54, 10:54] = 40
    # Bone region (> 250 HU)
    arr[8:24, 20:44, 20:44] = 600

    img = sitk.GetImageFromArray(arr)
    img.SetSpacing((1.0, 1.0, 2.0))
    file_path = str(tmp_path / "test_case_ct.nrrd")
    sitk.WriteImage(img, file_path)
    return file_path


def test_supported_command():
    """Verify that all whitelisted operations are recognized."""
    supported = get_supported_operations()
    assert "inspect_case" in supported
    assert "load_volume" in supported
    assert "segment" in supported
    assert "generate_model" in supported
    assert "export" in supported

    assert is_supported_operation("inspect_case") is True
    assert is_supported_operation("generate_model") is True
    assert is_supported_operation("arbitrary_hack_code") is False


def test_unsupported_command():
    """Verify that clinical diagnosis queries are strictly rejected with guidance."""
    diag_query = "Please diagnose if there is a malignant tumor or cancer in this CT scan."
    intent = RuleBasedParser.parse(diag_query)

    assert intent.is_supported is False
    assert intent.intent == "unsupported_clinical_request"
    assert "UNSUPPORTED REQUEST" in intent.unsupported_reason
    assert len(intent.operations) == 0


def test_copilot_parser_supported():
    """Verify natural language requests convert to structured operations."""
    query = "Prepare this CT scan and generate a 3D model of the spine bone"
    intent = RuleBasedParser.parse(query)

    assert intent.is_supported is True
    assert "inspect_case" in intent.operations
    assert "load_volume" in intent.operations
    assert "segment" in intent.operations
    assert "generate_model" in intent.operations
    assert intent.parameters.get("target_anatomy") == "bone"


def test_workflow_validation(sample_ct_path):
    """Verify CommandValidator passes a topologically valid workflow."""
    plan = WorkflowPlan(case_id="TEST_001")
    for op in ["inspect_case", "load_volume", "preprocess", "segment", "generate_model", "validate", "export"]:
        plan.add_step(WorkflowStep(operation=op, display_name=op))

    is_valid, messages, statuses = CommandValidator.validate_plan(plan, file_path=sample_ct_path)
    assert is_valid is True
    assert all(status == "PASS" for status in statuses.values())


def test_invalid_operation_order(sample_ct_path):
    """Verify CommandValidator flags invalid dependency ordering (e.g. model before volume)."""
    plan = WorkflowPlan(case_id="INVALID_001")
    # Placing generate_model and segment before load_volume
    plan.add_step(WorkflowStep(operation="generate_model", display_name="Generate Model"))
    plan.add_step(WorkflowStep(operation="load_volume", display_name="Load Volume"))

    is_valid, messages, statuses = CommandValidator.validate_plan(plan, file_path=sample_ct_path)
    assert is_valid is False
    assert statuses.get("generate_model") == "BLOCKED"
    assert any("requires prior completion" in m for m in messages)


def test_case_validation(sample_ct_path):
    """Verify CaseAnalyzer extracts valid dimensions and spacing metadata."""
    metadata = CaseAnalyzer.analyze_case(sample_ct_path)
    assert metadata.status == "VALID"
    assert metadata.file_format == "NRRD"
    assert metadata.modality == "CT"
    assert metadata.dimensions == (64, 64, 32)
    assert metadata.spacing == (1.0, 1.0, 2.0)


def test_validators():
    """Verify individual technical validators."""
    # VolumeValidator
    arr_3d = np.random.normal(50, 10, size=(10, 10, 10))
    ok, _ = VolumeValidator.validate(arr_3d)
    assert ok is True

    bad_arr = np.zeros((10, 10, 10))  # zero variance
    ok, _ = VolumeValidator.validate(bad_arr)
    assert ok is False

    # SegmentationValidator
    mask = np.zeros((10, 10, 10), dtype=np.uint8)
    mask[2:5, 2:5, 2:5] = 1
    ok, _ = SegmentationValidator.validate(mask, arr_3d)
    assert ok is True

    empty_mask = np.zeros((10, 10, 10), dtype=np.uint8)
    ok, _ = SegmentationValidator.validate(empty_mask, arr_3d)
    assert ok is False

    # OutputValidator
    ok, _ = OutputValidator.validate_mesh(100, 200)
    assert ok is True
    ok, _ = OutputValidator.validate_mesh(2, 1)
    assert ok is False


def test_manifest_generation(sample_ct_path):
    """Verify JSON Reproducibility Manifest output and integrity."""
    plan = WorkflowPlan(case_id="CASE_MANIFEST_TEST")
    step = WorkflowStep(operation="load_volume", display_name="Load Volume")
    step.complete("Loaded volume")
    plan.add_step(step)
    plan.final_status = OperationStatus.SUCCESS

    with tempfile.TemporaryDirectory() as tmpdir:
        out_files = {"test_out": os.path.join(tmpdir, "out.stl")}
        manifest_data = ManifestGenerator.generate_manifest(plan, sample_ct_path, out_files)
        manifest_file = os.path.join(tmpdir, "manifest.json")
        ManifestGenerator.save_manifest(manifest_data, manifest_file)

        assert os.path.exists(manifest_file)
        v_ok, _ = OutputValidator.validate_manifest(manifest_file)
        assert v_ok is True

        with open(manifest_file) as f:
            loaded = json.load(f)
            assert loaded["project"] == "SlicerFlow Copilot"
            assert loaded["case_id"] == "CASE_MANIFEST_TEST"
            assert loaded["final_status"] == "SUCCESS"
            assert "sha256" in loaded["input"]


def test_report_generation(sample_ct_path):
    """Verify Case Processing Report creation."""
    plan = WorkflowPlan(case_id="CASE_REPORT_TEST")
    s1 = WorkflowStep(operation="inspect_case", display_name="Case Inspection")
    s1.complete("Inspected")
    plan.add_step(s1)
    plan.final_status = OperationStatus.SUCCESS

    report_md = ReportGenerator.generate_markdown_report(plan, sample_ct_path, {})
    assert "SLICERFLOW COPILOT" in report_md
    assert "CASE_REPORT_TEST" in report_md
    assert "SAFETY DISCLAIMER" in report_md


def test_llm_client_fallback():
    """Verify ExternalLLMClient safely falls back to RuleBasedParser without API key."""
    client = ExternalLLMClient(api_key="")
    assert client.is_configured() is False

    intent = client.parse_workflow("Prepare this CT scan and reconstruct a 3D model")
    assert intent.is_supported is True
    assert "load_volume" in intent.operations
    assert "generate_model" in intent.operations


def test_slicer_code_generation(sample_ct_path):
    """Verify that clean 3D Slicer Python scripts are generated."""
    plan = WorkflowPlan(case_id="CASE_SCRIPT_TEST")
    for op in ["inspect_case", "load_volume", "segment", "generate_model", "export"]:
        plan.add_step(WorkflowStep(operation=op, display_name=op))

    script = SlicerCodeGenerator.generate_slicer_script(
        plan=plan,
        input_file_path=sample_ct_path,
        output_dir="C:/tmp/outputs"
    )
    assert "import slicer" in script
    assert "slicer.util.loadVolume" in script
    assert "vtkMRMLSegmentationNode" in script
    assert "ExportSegmentsClosedSurfaceRepresentationToFiles" in script


def test_end_to_end_orchestration(sample_ct_path):
    """Verify complete pipeline execution, status tracking, mesh extraction, and artifacts."""
    planner = WorkflowPlanner()
    intent = RuleBasedParser.parse("Prepare this CT scan and generate a 3D model")
    plan = planner.plan(intent, case_id="CASE_E2E_TEST", case_file_path=sample_ct_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        orchestrator = PipelineOrchestrator()
        result_plan = orchestrator.execute(
            plan=plan,
            file_path=sample_ct_path,
            output_dir=tmpdir
        )

        assert result_plan.final_status == OperationStatus.SUCCESS
        assert len(result_plan.steps) == 7
        assert all(s.status == OperationStatus.SUCCESS for s in result_plan.steps)

        # Check export files
        stl_path = os.path.join(tmpdir, "CASE_E2E_TEST_model.stl")
        manifest_path = os.path.join(tmpdir, "CASE_E2E_TEST_manifest.json")
        report_path = os.path.join(tmpdir, "CASE_E2E_TEST_processing_report.md")

        assert os.path.exists(stl_path)
        assert os.path.getsize(stl_path) > 0
        assert os.path.exists(manifest_path)
        assert os.path.exists(report_path)
