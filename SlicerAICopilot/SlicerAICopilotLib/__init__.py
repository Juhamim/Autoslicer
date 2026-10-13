"""Slicer AI Copilot - Natural language control for 3D Slicer."""

__version__ = "0.1.0"
__author__ = "Slicer AI Copilot Team"

# Core components
from .schemas import (
    ActionPlan, Action, SceneObject, SceneSummary,
    ALLOWED_ACTIONS, ACTION_CLASSES,
    ShowAction, HideAction, ShowOnlyAction, SetOpacityAction,
    SetColorAction, ResetDisplayAction, ResetViewAction,
    ZoomToAction, ViewAction, ListObjectsAction, ListVisibleObjectsAction,
    OpenFolderAction, ImportDicomAction, LoadVolumeAction,
    LoadModelAction, LoadSegmentationAction
)

from .scene_manager import SceneManager, get_scene_manager
from .action_engine import ActionEngine, ActionResult, get_action_engine
from .validator import Validator, ValidationError, get_validator
from .verification import Verifier, VerificationResult, get_verifier
from .llm_client import LLMClient, LLMResponse, get_llm_client
from .file_manager import FileManager, get_file_manager
from .utils import (
    fuzzy_match, resolve_target, find_matching_objects,
    get_file_type, scan_folder_for_files, group_dicom_series,
    format_scene_summary
)

__all__ = [
    # Schemas
    "ActionPlan", "Action", "SceneObject", "SceneSummary",
    "ALLOWED_ACTIONS", "ACTION_CLASSES",
    "ShowAction", "HideAction", "ShowOnlyAction", "SetOpacityAction",
    "SetColorAction", "ResetDisplayAction", "ResetViewAction",
    "ZoomToAction", "ViewAction", "ListObjectsAction", "ListVisibleObjectsAction",
    "OpenFolderAction", "ImportDicomAction", "LoadVolumeAction",
    "LoadModelAction", "LoadSegmentationAction",
    # Core
    "SceneManager", "get_scene_manager",
    "ActionEngine", "ActionResult", "get_action_engine",
    "Validator", "ValidationError", "get_validator",
    "Verifier", "VerificationResult", "get_verifier",
    "LLMClient", "LLMResponse", "get_llm_client",
    "FileManager", "get_file_manager",
    # Utils
    "fuzzy_match", "resolve_target", "find_matching_objects",
    "get_file_type", "scan_folder_for_files", "group_dicom_series",
    "format_scene_summary",
]