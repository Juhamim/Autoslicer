"""Unit tests for SceneManager."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'SlicerAICopilot'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from SlicerAICopilotLib.schemas import SceneSummary, SceneObject
from SlicerAICopilotLib.scene_manager import SceneManager


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


class MockMRMLNode:
    def __init__(self, name, node_class="vtkMRMLModelNode", visible=True, opacity=1.0, color=None):
        self._name = name
        self._class = node_class
        self._display_node = MockDisplayNode(visible, opacity, color)

    def GetName(self):
        return self._name

    def GetDisplayNode(self):
        return self._display_node

    def GetDisplayVisibility(self):
        return self._display_node.GetVisibility()


class MockScene:
    def __init__(self, nodes=None):
        self._nodes = nodes or {}

    def GetNodesByClass(self, node_class):
        result = MockNodeList()
        for node in self._nodes.values():
            if node._class == node_class:
                result.add(node)
        return result

    def GetNodesByName(self, name):
        result = MockNodeList()
        if name in self._nodes:
            result.add(self._nodes[name])
        return result


class MockNodeList:
    def __init__(self):
        self._items = []

    def add(self, node):
        self._items.append(node)

    def GetNumberOfItems(self):
        return len(self._items)

    def GetItemAsObject(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None


class TestSceneManager(unittest.TestCase):

    def setUp(self):
        self.sm = SceneManager()
        self.nodes = {
            "Liver": MockMRMLNode("Liver", "vtkMRMLModelNode", visible=True, opacity=0.3),
            "Tumor": MockMRMLNode("Tumor", "vtkMRMLModelNode", visible=True, opacity=1.0, color=[1.0, 0.0, 0.0]),
            "Skin": MockMRMLNode("Skin", "vtkMRMLModelNode", visible=False, opacity=1.0),
            "CT": MockMRMLNode("CT", "vtkMRMLScalarVolumeNode", visible=True),
            "Portal Vein": MockMRMLNode("Portal Vein", "vtkMRMLModelNode", visible=True),
        }
        self.mock_scene = MockScene(self.nodes)
        self.sm._scene = self.mock_scene

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_get_scene_summary(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        summary = self.sm.get_scene_summary()
        self.assertIsInstance(summary, SceneSummary)
        self.assertEqual(len(summary.models), 4)
        self.assertEqual(len(summary.volumes), 1)

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_get_volumes(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        volumes = self.sm.get_volumes()
        self.assertEqual(len(volumes), 1)
        self.assertEqual(volumes[0].name, "CT")
        self.assertEqual(volumes[0].type, "ScalarVolume")

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_get_models(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        models = self.sm.get_models()
        self.assertEqual(len(models), 4)
        names = [m.name for m in models]
        self.assertIn("Liver", names)
        self.assertIn("Tumor", names)

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_find_node_by_name_found(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        node = self.sm.find_node_by_name("Liver")
        self.assertIsNotNone(node)
        self.assertEqual(node.GetName(), "Liver")

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_find_node_by_name_not_found(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        node = self.sm.find_node_by_name("NonExistent")
        self.assertIsNone(node)

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_get_visibility(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        node = self.sm.find_node_by_name("Liver")
        self.assertTrue(self.sm.get_visibility(node))
        node = self.sm.find_node_by_name("Skin")
        self.assertFalse(self.sm.get_visibility(node))

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_get_opacity(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        node = self.sm.find_node_by_name("Liver")
        self.assertAlmostEqual(self.sm.get_opacity(node), 0.3)

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_set_visibility(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        node = self.sm.find_node_by_name("Liver")
        self.sm.set_visibility(node, False)
        self.assertFalse(self.sm.get_visibility(node))

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_set_opacity(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        node = self.sm.find_node_by_name("Liver")
        self.sm.set_opacity(node, 0.5)
        self.assertAlmostEqual(self.sm.get_opacity(node), 0.5)

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_set_color(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        node = self.sm.find_node_by_name("Tumor")
        self.sm.set_color(node, [0.0, 1.0, 0.0])
        display_node = node.GetDisplayNode()
        self.assertEqual(display_node.GetColor(), [0.0, 1.0, 0.0])

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_reset_display(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        node = self.sm.find_node_by_name("Liver")
        self.sm.set_visibility(node, False)
        self.sm.set_opacity(node, 0.5)
        self.sm.reset_display(node)
        self.assertTrue(self.sm.get_visibility(node))
        self.assertAlmostEqual(self.sm.get_opacity(node), 1.0)

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_get_all_object_names(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        names = self.sm.get_all_object_names()
        self.assertIn("Liver", names)
        self.assertIn("Tumor", names)
        self.assertIn("CT", names)
        self.assertIn("Skin", names)

    @patch('SlicerAICopilotLib.scene_manager.SLICER_AVAILABLE', True)
    @patch('SlicerAICopilotLib.scene_manager.slicer')
    def test_find_matching_targets(self, mock_slicer):
        mock_slicer.mrmlScene = self.mock_scene
        matches = self.sm.find_matching_targets("tumor")
        self.assertIn("Tumor", matches)

    def test_no_slicer_returns_empty(self):
        sm_no_slicer = SceneManager()
        sm_no_slicer._scene = None
        summary = sm_no_slicer.get_scene_summary()
        self.assertIsInstance(summary, SceneSummary)
        self.assertEqual(len(summary.volumes), 0)


if __name__ == '__main__':
    unittest.main()
