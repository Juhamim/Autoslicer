"""Unit tests for ActionEngine."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'SlicerAICopilot'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import Mock, MagicMock, patch

from SlicerAICopilotLib.schemas import (
    ActionPlan, ShowAction, HideAction, ShowOnlyAction, SetOpacityAction,
    SetColorAction, ResetDisplayAction, ResetViewAction, ZoomToAction,
    ListObjectsAction, ListVisibleObjectsAction, ViewAction
)
from SlicerAICopilotLib.action_engine import ActionEngine, ActionResult


class MockDisplayNode:
    def __init__(self, visible=True, opacity=1.0, color=None):
        self._visible = visible
        self._opacity = opacity
        self._color = color or [1.0, 1.0, 1.0]

    def GetVisibility(self):
        return self._visible

    def SetVisibility(self, visible):
        self._visible = visible

    def GetOpacity(self):
        return self._opacity

    def SetOpacity(self, opacity):
        self._opacity = opacity

    def GetColor(self):
        return self._color

    def SetColor(self, r, g, b):
        self._color = [r, g, b]


class MockNode:
    def __init__(self, name):
        self.name = name
        self._display_node = MockDisplayNode()

    def GetDisplayNode(self):
        return self._display_node


class MockSceneManager:
    """Mock scene manager for testing."""
    
    def __init__(self):
        self.nodes = {}
        self.visibility = {}
        self.opacity = {}
        self.color = {}
        
        for name in ["Liver", "Tumor", "Skin", "Portal Vein", "Vena Cava", "Bone", "CT"]:
            self.nodes[name] = MockNode(name)
            self.visibility[name] = True
            self.opacity[name] = 1.0
            self.color[name] = [1.0, 1.0, 1.0]
    
    def find_node_by_name(self, name):
        return self.nodes.get(name)
    
    def find_matching_targets(self, query):
        query_lower = query.lower().replace(" ", "")
        return [name for name in self.nodes if query_lower in name.lower().replace(" ", "")]
    
    def get_all_object_names(self):
        return list(self.nodes.keys())
    
    def get_volumes(self):
        from SlicerAICopilotLib.schemas import SceneObject
        return [SceneObject(name="CT", type="ScalarVolume", visible=True)]
    
    def get_models(self):
        from SlicerAICopilotLib.schemas import SceneObject
        return [SceneObject(name=n, type="Model", visible=self.visibility.get(n, True),
                            opacity=self.opacity.get(n), color=self.color.get(n))
                for n in ["Liver", "Tumor", "Skin", "Portal Vein", "Vena Cava", "Bone"]]
    
    def get_segmentations(self):
        return []
    
    def get_markups(self):
        return []
    
    def get_transforms(self):
        return []
    
    def get_scene_summary(self):
        from SlicerAICopilotLib.schemas import SceneSummary
        return SceneSummary(
            volumes=self.get_volumes(),
            models=self.get_models(),
            segmentations=[],
            markups=[],
            transforms=[]
        )
    
    def get_visibility(self, node):
        return self.visibility.get(node.name, True)
    
    def get_opacity(self, node):
        return self.opacity.get(node.name)
    
    def set_visibility(self, node, visible):
        self.visibility[node.name] = visible
        return True
    
    def set_opacity(self, node, opacity):
        self.opacity[node.name] = opacity
        return True
    
    def set_color(self, node, color):
        self.color[node.name] = color
        return True
    
    def reset_display(self, node):
        self.visibility[node.name] = True
        self.opacity[node.name] = 1.0
        return True


class MockFileManager:
    """Mock file manager."""
    
    def scan_folder(self, path):
        return {"dicom_series_groups": [], "nifti_files": [], "nrrd_files": [], "model_files": [], "other_files": []}
    
    def import_case(self, scan_result, selections):
        return {"success": True, "imported": [], "failed": []}


class TestActionEngine(unittest.TestCase):
    
    def setUp(self):
        self.engine = ActionEngine()
        self.engine.scene_manager = MockSceneManager()
        self.engine.file_manager = MockFileManager()
    
    def test_execute_show(self):
        action = ShowAction(type="SHOW", target="Skin")
        result = self.engine.execute_action(action)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Shown: Skin")
        self.assertTrue(self.engine.scene_manager.visibility["Skin"])
    
    def test_execute_hide(self):
        action = HideAction(type="HIDE", target="Skin")
        result = self.engine.execute_action(action)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Hidden: Skin")
        self.assertFalse(self.engine.scene_manager.visibility["Skin"])
    
    def test_execute_show_only(self):
        action = ShowOnlyAction(type="SHOW_ONLY", targets=["Tumor", "Portal Vein"])
        result = self.engine.execute_action(action)
        self.assertTrue(result.success)
        # Tumor and Portal Vein should be visible
        self.assertTrue(self.engine.scene_manager.visibility["Tumor"])
        self.assertTrue(self.engine.scene_manager.visibility["Portal Vein"])
        # Others should be hidden
        self.assertFalse(self.engine.scene_manager.visibility["Liver"])
        self.assertFalse(self.engine.scene_manager.visibility["Skin"])
        self.assertFalse(self.engine.scene_manager.visibility["Bone"])
    
    def test_execute_set_opacity(self):
        action = SetOpacityAction(type="SET_OPACITY", target="Liver", value=0.3)
        result = self.engine.execute_action(action)
        self.assertTrue(result.success)
        self.assertEqual(self.engine.scene_manager.opacity["Liver"], 0.3)
    
    def test_execute_set_color(self):
        action = SetColorAction(type="SET_COLOR", target="Tumor", color=[1.0, 0.0, 0.0])
        result = self.engine.execute_action(action)
        self.assertTrue(result.success)
        self.assertEqual(self.engine.scene_manager.color["Tumor"], [1.0, 0.0, 0.0])
    
    def test_execute_reset_display(self):
        # First change some properties
        self.engine.scene_manager.visibility["Liver"] = False
        self.engine.scene_manager.opacity["Liver"] = 0.5
        
        action = ResetDisplayAction(type="RESET_DISPLAY", target="Liver")
        result = self.engine.execute_action(action)
        self.assertTrue(result.success)
        self.assertTrue(self.engine.scene_manager.visibility["Liver"])
        self.assertEqual(self.engine.scene_manager.opacity["Liver"], 1.0)
    
    def test_execute_list_objects(self):
        action = ListObjectsAction(type="LIST_OBJECTS")
        result = self.engine.execute_action(action)
        self.assertTrue(result.success)
        self.assertIn("CT", result.message)
        self.assertIn("Liver", result.message)
    
    def test_execute_list_visible_objects(self):
        action = ListVisibleObjectsAction(type="LIST_VISIBLE_OBJECTS")
        result = self.engine.execute_action(action)
        self.assertTrue(result.success)
    
    def test_unknown_target(self):
        action = ShowAction(type="SHOW", target="NonExistent")
        result = self.engine.execute_action(action)
        self.assertFalse(result.success)
        self.assertIn("not found", result.message)
    
    def test_ambiguous_target(self):
        # Replace single Tumor with two numbered tumors to create ambiguity
        del self.engine.scene_manager.nodes["Tumor"]
        self.engine.scene_manager.nodes["Tumor 1"] = MockNode("Tumor 1")
        self.engine.scene_manager.nodes["Tumor 2"] = MockNode("Tumor 2")
        self.engine.scene_manager.visibility["Tumor 1"] = True
        self.engine.scene_manager.visibility["Tumor 2"] = True
        self.engine.scene_manager.opacity["Tumor 1"] = 1.0
        self.engine.scene_manager.opacity["Tumor 2"] = 1.0
        
        action = ShowAction(type="SHOW", target="Tumor")
        result = self.engine.execute_action(action)
        self.assertFalse(result.success)
        self.assertIn("Ambiguous", result.message)
    
    def test_execute_plan(self):
        plan = ActionPlan(
            version="1.0",
            reply="Test plan",
            actions=[
                HideAction(type="HIDE", target="Skin"),
                ShowAction(type="SHOW", target="Tumor"),
                SetOpacityAction(type="SET_OPACITY", target="Liver", value=0.3)
            ]
        )
        results = self.engine.execute_plan(plan)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))
        self.assertFalse(self.engine.scene_manager.visibility["Skin"])
        self.assertTrue(self.engine.scene_manager.visibility["Tumor"])
        self.assertEqual(self.engine.scene_manager.opacity["Liver"], 0.3)
    
    def test_execute_plan_stops_on_failure(self):
        plan = ActionPlan(
            version="1.0",
            reply="Test plan",
            actions=[
                HideAction(type="HIDE", target="Skin"),
                ShowAction(type="SHOW", target="NonExistent"),  # This will fail
                ShowAction(type="SHOW", target="Tumor")  # This should not execute
            ]
        )
        results = self.engine.execute_plan(plan)
        self.assertEqual(len(results), 2)  # Stops after failure
        self.assertTrue(results[0].success)
        self.assertFalse(results[1].success)


if __name__ == '__main__':
    unittest.main()