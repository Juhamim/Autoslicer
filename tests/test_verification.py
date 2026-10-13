"""Unit tests for Verifier."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'SlicerAICopilot'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import Mock

from SlicerAICopilotLib.schemas import (
    ShowAction, HideAction, ShowOnlyAction, SetOpacityAction,
    SetColorAction, ResetDisplayAction, ZoomToAction, ViewAction,
)
from SlicerAICopilotLib.action_engine import ActionResult
from SlicerAICopilotLib.verification import Verifier, VerificationResult


class MockDisplayNode:
    def __init__(self, visible=True, opacity=1.0, color=None):
        self._visible = visible
        self._opacity = opacity
        self._color = color or [1.0, 1.0, 1.0]

    def GetVisibility(self):
        return self._visible

    def GetOpacity(self):
        return self._opacity

    def GetColor(self):
        return self._color


class MockNode:
    def __init__(self, name):
        self.name = name
        self._display_node = MockDisplayNode()

    def GetDisplayNode(self):
        return self._display_node


class MockSceneManager:
    def __init__(self):
        self.nodes = {}
        self.visibility = {}
        self.opacity = {}

        for name in ["Liver", "Tumor", "Skin", "Portal Vein", "Vena Cava", "Bone", "CT"]:
            self.nodes[name] = MockNode(name)
            self.visibility[name] = True
            self.opacity[name] = 1.0

    def find_node_by_name(self, name):
        return self.nodes.get(name)

    def find_matching_targets(self, query):
        query_lower = query.lower().replace(" ", "")
        return [name for name in self.nodes if query_lower in name.lower().replace(" ", "")]

    def get_volumes(self):
        from SlicerAICopilotLib.schemas import SceneObject
        return [SceneObject(name="CT", type="ScalarVolume", visible=True)]

    def get_models(self):
        from SlicerAICopilotLib.schemas import SceneObject
        return [SceneObject(name=n, type="Model", visible=self.visibility.get(n, True),
                            opacity=self.opacity.get(n))
                for n in ["Liver", "Tumor", "Skin", "Portal Vein", "Vena Cava", "Bone"]]

    def get_segmentations(self):
        return []

    def get_visibility(self, node):
        return self.visibility.get(node.name, True)

    def get_opacity(self, node):
        return self.opacity.get(node.name)

    def set_color(self, node, color):
        node._display_node._color = color
        return True


class TestVerifier(unittest.TestCase):

    def setUp(self):
        self.verifier = Verifier()
        self.verifier.scene_manager = MockSceneManager()

    def test_verify_show_passes_when_visible(self):
        action = ShowAction(type="SHOW", target="Tumor")
        result = ActionResult(True, "Shown: Tumor")
        vr = self.verifier.verify_action(action, result)
        self.assertTrue(vr.passed)
        self.assertIn("visible", vr.message.lower())

    def test_verify_show_fails_when_hidden(self):
        self.verifier.scene_manager.visibility["Tumor"] = False
        action = ShowAction(type="SHOW", target="Tumor")
        result = ActionResult(True, "Shown: Tumor")
        vr = self.verifier.verify_action(action, result)
        self.assertFalse(vr.passed)

    def test_verify_show_fails_when_not_found(self):
        action = ShowAction(type="SHOW", target="NonExistent")
        result = ActionResult(True, "Shown: NonExistent")
        vr = self.verifier.verify_action(action, result)
        self.assertFalse(vr.passed)

    def test_verify_hide_passes_when_hidden(self):
        self.verifier.scene_manager.visibility["Skin"] = False
        action = HideAction(type="HIDE", target="Skin")
        result = ActionResult(True, "Hidden: Skin")
        vr = self.verifier.verify_action(action, result)
        self.assertTrue(vr.passed)
        self.assertIn("hidden", vr.message.lower())

    def test_verify_hide_fails_when_still_visible(self):
        action = HideAction(type="HIDE", target="Skin")
        result = ActionResult(True, "Hidden: Skin")
        vr = self.verifier.verify_action(action, result)
        self.assertFalse(vr.passed)

    def test_verify_hide_fails_when_not_found(self):
        action = HideAction(type="HIDE", target="NonExistent")
        result = ActionResult(True, "Hidden: NonExistent")
        vr = self.verifier.verify_action(action, result)
        self.assertFalse(vr.passed)

    def test_verify_show_only_passes(self):
        self.verifier.scene_manager.visibility["Tumor"] = True
        self.verifier.scene_manager.visibility["Portal Vein"] = True
        self.verifier.scene_manager.visibility["Liver"] = False
        self.verifier.scene_manager.visibility["Skin"] = False
        self.verifier.scene_manager.visibility["Bone"] = False
        self.verifier.scene_manager.visibility["Vena Cava"] = False
        self.verifier.scene_manager.visibility["CT"] = False

        action = ShowOnlyAction(type="SHOW_ONLY", targets=["Tumor", "Portal Vein"])
        result = ActionResult(True, "Showing only: Tumor, Portal Vein")
        vr = self.verifier.verify_action(action, result)
        self.assertTrue(vr.passed)

    def test_verify_show_only_fails_when_targets_not_found(self):
        action = ShowOnlyAction(type="SHOW_ONLY", targets=["NonExistent"])
        result = ActionResult(True, "Showing only: NonExistent")
        vr = self.verifier.verify_action(action, result)
        self.assertFalse(vr.passed)

    def test_verify_set_opacity_passes(self):
        self.verifier.scene_manager.opacity["Liver"] = 0.3
        action = SetOpacityAction(type="SET_OPACITY", target="Liver", value=0.3)
        result = ActionResult(True, "Set opacity")
        vr = self.verifier.verify_action(action, result)
        self.assertTrue(vr.passed)

    def test_verify_set_opacity_fails_when_wrong_value(self):
        self.verifier.scene_manager.opacity["Liver"] = 0.8
        action = SetOpacityAction(type="SET_OPACITY", target="Liver", value=0.3)
        result = ActionResult(True, "Set opacity")
        vr = self.verifier.verify_action(action, result)
        self.assertFalse(vr.passed)

    def test_verify_set_opacity_fails_when_not_found(self):
        action = SetOpacityAction(type="SET_OPACITY", target="NonExistent", value=0.3)
        result = ActionResult(True, "Set opacity")
        vr = self.verifier.verify_action(action, result)
        self.assertFalse(vr.passed)

    def test_verify_set_color_passes(self):
        self.verifier.scene_manager.nodes["Tumor"]._display_node._color = [1.0, 0.0, 0.0]
        action = SetColorAction(type="SET_COLOR", target="Tumor", color=[1.0, 0.0, 0.0])
        result = ActionResult(True, "Set color")
        vr = self.verifier.verify_action(action, result)
        self.assertTrue(vr.passed)

    def test_verify_set_color_fails_when_not_found(self):
        action = SetColorAction(type="SET_COLOR", target="NonExistent", color=[1.0, 0.0, 0.0])
        result = ActionResult(True, "Set color")
        vr = self.verifier.verify_action(action, result)
        self.assertFalse(vr.passed)

    def test_verify_reset_display_passes(self):
        action = ResetDisplayAction(type="RESET_DISPLAY", target="Liver")
        result = ActionResult(True, "Reset display")
        vr = self.verifier.verify_action(action, result)
        self.assertTrue(vr.passed)

    def test_verify_reset_display_fails_when_not_found(self):
        action = ResetDisplayAction(type="RESET_DISPLAY", target="NonExistent")
        result = ActionResult(True, "Reset display")
        vr = self.verifier.verify_action(action, result)
        self.assertFalse(vr.passed)

    def test_verify_zoom_to_passes(self):
        action = ZoomToAction(type="ZOOM_TO", target="Tumor")
        result = ActionResult(True, "Zoomed to: Tumor")
        vr = self.verifier.verify_action(action, result)
        self.assertTrue(vr.passed)

    def test_verify_zoom_to_fails_when_not_found(self):
        action = ZoomToAction(type="ZOOM_TO", target="NonExistent")
        result = ActionResult(True, "Zoomed to: NonExistent")
        vr = self.verifier.verify_action(action, result)
        self.assertFalse(vr.passed)

    def test_verify_view_passes(self):
        action = ViewAction(type="AXIAL_VIEW")
        result = ActionResult(True, "Switched to axial view")
        vr = self.verifier.verify_action(action, result)
        self.assertTrue(vr.passed)

    def test_verify_plan_passes_for_successful_actions(self):
        self.verifier.scene_manager.visibility["Skin"] = False
        plan_actions = [
            ShowAction(type="SHOW", target="Tumor"),
            HideAction(type="HIDE", target="Skin"),
        ]
        action_results = [
            ActionResult(True, "Shown: Tumor"),
            ActionResult(True, "Hidden: Skin"),
        ]
        vr_list = self.verifier.verify_plan(plan_actions, action_results)
        self.assertEqual(len(vr_list), 2)
        self.assertTrue(all(vr.passed for vr in vr_list))

    def test_verify_plan_fails_for_failed_actions(self):
        plan_actions = [
            ShowAction(type="SHOW", target="Tumor"),
            ShowAction(type="SHOW", target="NonExistent"),
        ]
        action_results = [
            ActionResult(True, "Shown: Tumor"),
            ActionResult(False, "Object 'NonExistent' not found"),
        ]
        vr_list = self.verifier.verify_plan(plan_actions, action_results)
        self.assertEqual(len(vr_list), 2)
        self.assertTrue(vr_list[0].passed)
        self.assertFalse(vr_list[1].passed)


if __name__ == '__main__':
    unittest.main()
