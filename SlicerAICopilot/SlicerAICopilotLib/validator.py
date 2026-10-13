"""Validator - Validates action plans before execution."""

from typing import List, Tuple, Optional, Any
from .schemas import (
    ActionPlan, Action, ALLOWED_ACTIONS, ACTION_CLASSES,
    ShowAction, HideAction, ShowOnlyAction, SetOpacityAction,
    SetColorAction, ResetDisplayAction, ResetViewAction,
    ZoomToAction, ViewAction, ListObjectsAction, ListVisibleObjectsAction,
    OpenFolderAction, ImportDicomAction, LoadVolumeAction,
    LoadModelAction, LoadSegmentationAction
)
from .scene_manager import get_scene_manager
from .utils import find_matching_objects


class ValidationError(Exception):
    """Raised when validation fails."""
    def __init__(self, message: str, errors: List[str] = None):
        super().__init__(message)
        self.errors = errors or []


class Validator:
    """Validates action plans for safety and correctness."""
    
    def __init__(self):
        self.scene_manager = get_scene_manager()
    
    def validate_plan(self, plan: ActionPlan) -> Tuple[bool, List[str]]:
        """Validate an entire action plan.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if not plan.actions:
            errors.append("Action plan contains no actions")
            return False, errors
        
        for i, action in enumerate(plan.actions):
            valid, action_errors = self.validate_action(action)
            if not valid:
                for err in action_errors:
                    errors.append(f"Action {i+1} ({action.type}): {err}")
        
        return len(errors) == 0, errors
    
    def validate_action(self, action: Action) -> Tuple[bool, List[str]]:
        """Validate a single action.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if action.type not in ALLOWED_ACTIONS:
            errors.append(f"Action type '{action.type}' is not allowed")
            return False, errors
        
        action_class = ACTION_CLASSES.get(action.type)
        if not action_class:
            errors.append(f"No validator for action type: {action.type}")
            return False, errors
        
        if action.type in ["SHOW", "HIDE", "SET_OPACITY", "SET_COLOR", "RESET_DISPLAY", "ZOOM_TO"]:
            errors.extend(self._validate_single_target(action))
        elif action.type == "SHOW_ONLY":
            errors.extend(self._validate_multi_target(action))
        
        if action.type == "SET_OPACITY":
            errors.extend(self._validate_opacity(action))
        elif action.type == "SET_COLOR":
            errors.extend(self._validate_color(action))
        
        return len(errors) == 0, errors
    
    def _validate_single_target(self, action: Action) -> List[str]:
        errors = []
        target = getattr(action, 'target', None)
        
        if not target:
            errors.append("Missing required field: target")
            return errors
        
        if not self._target_exists(target):
            matches = self.scene_manager.find_matching_targets(target)
            if matches:
                action.target = matches[0]
            else:
                errors.append(f"Target '{target}' not found in scene")
        
        return errors
    
    def _validate_multi_target(self, action: ShowOnlyAction) -> List[str]:
        errors = []
        targets = action.targets
        
        if not targets:
            errors.append("SHOW_ONLY requires at least one target")
            return errors
        
        corrected = []
        for target in targets:
            if not self._target_exists(target):
                matches = self.scene_manager.find_matching_targets(target)
                if matches:
                    corrected.append(matches[0])
                else:
                    errors.append(f"Target '{target}' not found in scene")
            else:
                corrected.append(target)
        
        if corrected and not errors:
            action.targets = corrected
        
        return errors
    
    def _validate_opacity(self, action: SetOpacityAction) -> List[str]:
        errors = []
        value = action.value
        
        if value < 0.0 or value > 1.0:
            errors.append(f"Opacity value must be between 0.0 and 1.0, got: {value}")
        
        return errors
    
    def _validate_color(self, action: SetColorAction) -> List[str]:
        errors = []
        color = action.color
        
        if len(color) != 3:
            errors.append(f"Color must have 3 components (RGB), got: {len(color)}")
        
        for i, component in enumerate(color):
            if component < 0.0 or component > 1.0:
                errors.append(f"Color component {i} must be between 0.0 and 1.0, got: {component}")
        
        return errors
    
    def _target_exists(self, target: str) -> bool:
        """Check if a target exists in the scene (exact match)."""
        node = self.scene_manager.find_node_by_name(target)
        return node is not None
    
    def validate_json(self, json_str: str) -> Tuple[bool, Optional[ActionPlan], List[str]]:
        """Validate and parse a JSON action plan string."""
        import json
        
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return False, None, [f"Invalid JSON: {str(e)}"]
        
        try:
            plan = ActionPlan.model_validate(data)
        except Exception as e:
            return False, None, [f"Schema validation failed: {str(e)}"]
        
        valid, errors = self.validate_plan(plan)
        return valid, plan, errors
    
    def check_for_malicious_content(self, json_str: str) -> List[str]:
        """Check for potentially malicious content in model output."""
        errors = []
        
        dangerous_patterns = [
            "exec(",
            "eval(",
            "__import__",
            "subprocess",
            "os.system",
            "open(",
            "file(",
            "compile(",
            "lambda",
            "__class__",
            "__bases__",
            "__subclasses__",
            "import os",
            "import sys",
            "import subprocess",
            "from os",
            "from sys",
        ]
        
        lower_str = json_str.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in lower_str:
                errors.append(f"Potentially dangerous pattern detected: {pattern}")
        
        return errors


_validator_instance = None


def get_validator() -> Validator:
    """Get the global validator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = Validator()
    return _validator_instance