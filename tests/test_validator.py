"""Unit tests for Validator."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'SlicerAICopilot'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import Mock, MagicMock, patch

from SlicerAICopilotLib.schemas import (
    ActionPlan, ShowAction, HideAction, ShowOnlyAction, SetOpacityAction,
    SetColorAction, ResetDisplayAction, ResetViewAction, ZoomToAction,
    ListObjectsAction, ListVisibleObjectsAction
)
from SlicerAICopilotLib.validator import Validator, ValidationError


class MockSceneManager:
    """Mock scene manager for testing."""
    
    def __init__(self, objects=None):
        self.objects = objects or ["Liver", "Tumor", "Skin", "Portal Vein", "Vena Cava", "Bone", "CT"]
    
    def find_node_by_name(self, name):
        if name in self.objects:
            return Mock(name=name)
        return None
    
    def find_matching_targets(self, query):
        query_lower = query.lower().replace(" ", "")
        return [obj for obj in self.objects if query_lower in obj.lower().replace(" ", "")]


class TestValidator(unittest.TestCase):
    
    def setUp(self):
        self.validator = Validator()
        self.validator.scene_manager = MockSceneManager()
    
    def test_valid_show_action(self):
        action = ShowAction(type="SHOW", target="Liver")
        valid, errors = self.validator.validate_action(action)
        self.assertTrue(valid)
        self.assertEqual(errors, [])
    
    def test_valid_hide_action(self):
        action = HideAction(type="HIDE", target="Skin")
        valid, errors = self.validator.validate_action(action)
        self.assertTrue(valid)
    
    def test_valid_show_only_action(self):
        action = ShowOnlyAction(type="SHOW_ONLY", targets=["Tumor", "Portal Vein"])
        valid, errors = self.validator.validate_action(action)
        self.assertTrue(valid)
    
    def test_valid_set_opacity(self):
        action = SetOpacityAction(type="SET_OPACITY", target="Liver", value=0.3)
        valid, errors = self.validator.validate_action(action)
        self.assertTrue(valid)
    
    def test_invalid_opacity_too_high(self):
        json_str = '{"version":"1.0","reply":"test","actions":[{"type":"SET_OPACITY","target":"Liver","value":1.5}]}'
        valid, plan, errors = self.validator.validate_json(json_str)
        self.assertFalse(valid)
        self.assertTrue(any("Opacity" in e or "1.5" in e for e in errors))
    
    def test_invalid_opacity_too_low(self):
        json_str = '{"version":"1.0","reply":"test","actions":[{"type":"SET_OPACITY","target":"Liver","value":-0.1}]}'
        valid, plan, errors = self.validator.validate_json(json_str)
        self.assertFalse(valid)
    
    def test_valid_set_color(self):
        action = SetColorAction(type="SET_COLOR", target="Tumor", color=[1.0, 0.0, 0.0])
        valid, errors = self.validator.validate_action(action)
        self.assertTrue(valid)
    
    def test_invalid_color_components(self):
        json_str = '{"version":"1.0","reply":"test","actions":[{"type":"SET_COLOR","target":"Tumor","color":[1.5,0.0,0.0]}]}'
        valid, plan, errors = self.validator.validate_json(json_str)
        self.assertFalse(valid)
        self.assertTrue(any("Color component" in e or "between" in e for e in errors))
    
    def test_invalid_color_length(self):
        json_str = '{"version":"1.0","reply":"test","actions":[{"type":"SET_COLOR","target":"Tumor","color":[1.0,0.0]}]}'
        valid, plan, errors = self.validator.validate_json(json_str)
        self.assertFalse(valid)
    
    def test_unknown_target(self):
        action = ShowAction(type="SHOW", target="NonExistent")
        valid, errors = self.validator.validate_action(action)
        self.assertFalse(valid)
        self.assertTrue(any("not found" in e for e in errors))
    
    def test_unknown_action_type(self):
        json_str = '{"version":"1.0","reply":"test","actions":[{"type":"INVALID_ACTION","target":"Liver"}]}'
        valid, plan, errors = self.validator.validate_json(json_str)
        self.assertFalse(valid)
    
    def test_missing_target(self):
        action = ShowAction(type="SHOW", target="")
        valid, errors = self.validator.validate_action(action)
        self.assertFalse(valid)
        self.assertTrue(any("Missing required field: target" in e for e in errors))
    
    def test_empty_plan(self):
        plan = ActionPlan(version="1.0", reply="test", actions=[])
        valid, errors = self.validator.validate_plan(plan)
        self.assertFalse(valid)
        self.assertTrue(any("no actions" in e for e in errors))
    
    def test_ambiguous_target_detection(self):
        # Scene has multiple tumors - auto-corrects to first match
        self.validator.scene_manager = MockSceneManager(["Tumor 1", "Tumor 2", "Liver"])
        action = ShowAction(type="SHOW", target="Tumor")
        valid, errors = self.validator.validate_action(action)
        self.assertTrue(valid)
        self.assertEqual(action.target, "Tumor 1")
    
    def test_validate_json_valid(self):
        json_str = '''
        {
          "version": "1.0",
          "reply": "Hiding skin",
          "actions": [{"type": "HIDE", "target": "Skin"}]
        }
        '''
        valid, plan, errors = self.validator.validate_json(json_str)
        self.assertTrue(valid)
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.actions), 1)
    
    def test_validate_json_invalid(self):
        json_str = '{"version": "1.0", "actions": []}'
        valid, plan, errors = self.validator.validate_json(json_str)
        self.assertFalse(valid)
    
    def test_validate_json_malformed(self):
        json_str = '{invalid json}'
        valid, plan, errors = self.validator.validate_json(json_str)
        self.assertFalse(valid)
        self.assertTrue(any("Invalid JSON" in e for e in errors))
    
    def test_malicious_content_detection(self):
        malicious = '{"actions": [{"type": "SHOW", "target": "__import__(\"os\").system(\"rm -rf /\")"}]}'
        errors = self.validator.check_for_malicious_content(malicious)
        self.assertTrue(len(errors) > 0)
    
    def test_valid_full_plan(self):
        plan = ActionPlan(
            version="1.0",
            reply="Preparing case",
            actions=[
                ShowAction(type="SHOW", target="CT"),
                ShowOnlyAction(type="SHOW_ONLY", targets=["Tumor", "Portal Vein"]),
                SetOpacityAction(type="SET_OPACITY", target="Liver", value=0.3),
                ZoomToAction(type="ZOOM_TO", target="Tumor")
            ]
        )
        valid, errors = self.validator.validate_plan(plan)
        self.assertTrue(valid)
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()