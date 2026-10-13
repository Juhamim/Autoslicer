"""Scene Manager - Inspects and queries the 3D Slicer MRML scene."""

try:
    import slicer
    from slicer import vtkMRMLScene, vtkMRMLScalarVolumeNode, vtkMRMLModelNode
    from slicer import vtkMRMLSegmentationNode, vtkMRMLMarkupsNode, vtkMRMLTransformNode
    SLICER_AVAILABLE = True
except ImportError:
    SLICER_AVAILABLE = False
    slicer = None

from typing import List, Dict, Optional, Any
from .schemas import SceneObject, SceneSummary
from .utils import fuzzy_match, resolve_target, find_matching_objects


class SceneManager:
    """Manages interaction with the Slicer MRML scene."""
    
    def __init__(self):
        self._scene = None
    
    @property
    def scene(self):
        """Get the current MRML scene."""
        if SLICER_AVAILABLE and slicer.mrmlScene:
            return slicer.mrmlScene
        return None
    
    def get_scene_summary(self) -> SceneSummary:
        """Get a complete summary of the current scene."""
        if not SLICER_AVAILABLE or not self.scene:
            return SceneSummary()
        
        summary = SceneSummary()
        summary.volumes = self.get_volumes()
        summary.models = self.get_models()
        summary.segmentations = self.get_segmentations()
        summary.markups = self.get_markups()
        summary.transforms = self.get_transforms()
        return summary
    
    def get_volumes(self) -> List[SceneObject]:
        """Get all scalar volume nodes."""
        if not SLICER_AVAILABLE or not self.scene:
            return []
        
        volumes = []
        volume_nodes = self.scene.GetNodesByClass("vtkMRMLScalarVolumeNode")
        for i in range(volume_nodes.GetNumberOfItems()):
            node = volume_nodes.GetItemAsObject(i)
            if node:
                volumes.append(SceneObject(
                    name=node.GetName(),
                    type="ScalarVolume",
                    visible=node.GetDisplayVisibility() if hasattr(node, 'GetDisplayVisibility') else True
                ))
        return volumes
    
    def get_models(self) -> List[SceneObject]:
        """Get all model nodes."""
        if not SLICER_AVAILABLE or not self.scene:
            return []
        
        models = []
        model_nodes = self.scene.GetNodesByClass("vtkMRMLModelNode")
        for i in range(model_nodes.GetNumberOfItems()):
            node = model_nodes.GetItemAsObject(i)
            if node:
                display_node = node.GetDisplayNode()
                visible = True
                opacity = None
                color = None
                if display_node:
                    visible = display_node.GetVisibility()
                    opacity = display_node.GetOpacity()
                    color = list(display_node.GetColor())
                models.append(SceneObject(
                    name=node.GetName(),
                    type="Model",
                    visible=visible,
                    opacity=opacity,
                    color=color
                ))
        return models
    
    def get_segmentations(self) -> List[SceneObject]:
        """Get all segmentation nodes."""
        if not SLICER_AVAILABLE or not self.scene:
            return []
        
        segmentations = []
        seg_nodes = self.scene.GetNodesByClass("vtkMRMLSegmentationNode")
        for i in range(seg_nodes.GetNumberOfItems()):
            node = seg_nodes.GetItemAsObject(i)
            if node:
                display_node = node.GetDisplayNode()
                visible = True
                opacity = None
                if display_node:
                    visible = display_node.GetVisibility()
                    opacity = display_node.GetOpacity()
                segmentations.append(SceneObject(
                    name=node.GetName(),
                    type="Segmentation",
                    visible=visible,
                    opacity=opacity
                ))
        return segmentations
    
    def get_markups(self) -> List[SceneObject]:
        """Get all markups nodes."""
        if not SLICER_AVAILABLE or not self.scene:
            return []
        
        markups = []
        markup_nodes = self.scene.GetNodesByClass("vtkMRMLMarkupsNode")
        for i in range(markup_nodes.GetNumberOfItems()):
            node = markup_nodes.GetItemAsObject(i)
            if node:
                display_node = node.GetDisplayNode()
                visible = True
                if display_node:
                    visible = display_node.GetVisibility()
                markups.append(SceneObject(
                    name=node.GetName(),
                    type="Markups",
                    visible=visible
                ))
        return markups
    
    def get_transforms(self) -> List[SceneObject]:
        """Get all transform nodes."""
        if not SLICER_AVAILABLE or not self.scene:
            return []
        
        transforms = []
        transform_nodes = self.scene.GetNodesByClass("vtkMRMLTransformNode")
        for i in range(transform_nodes.GetNumberOfItems()):
            node = transform_nodes.GetItemAsObject(i)
            if node:
                transforms.append(SceneObject(
                    name=node.GetName(),
                    type="Transform",
                    visible=True
                ))
        return transforms
    
    def find_node_by_name(self, name: str):
        """Find a node by exact name match."""
        if not SLICER_AVAILABLE or not self.scene:
            return None
        
        nodes = self.scene.GetNodesByName(name)
        if nodes.GetNumberOfItems() > 0:
            return nodes.GetItemAsObject(0)
        return None
    
    def find_nodes_by_type(self, node_type: str) -> List:
        """Find all nodes of a given type."""
        if not SLICER_AVAILABLE or not self.scene:
            return []
        
        nodes = self.scene.GetNodesByClass(node_type)
        result = []
        for i in range(nodes.GetNumberOfItems()):
            node = nodes.GetItemAsObject(i)
            if node:
                result.append(node)
        return result
    
    def get_all_object_names(self) -> List[str]:
        """Get names of all scene objects."""
        summary = self.get_scene_summary()
        names = []
        for category in [summary.volumes, summary.models, summary.segmentations, summary.markups, summary.transforms]:
            names.extend([obj.name for obj in category])
        return names
    
    def resolve_target(self, query: str) -> Optional[str]:
        """Resolve a natural language query to a single object name."""
        all_names = self.get_all_object_names()
        return resolve_target(query, all_names)
    
    def find_matching_targets(self, query: str) -> List[str]:
        """Find all objects matching a query."""
        all_names = self.get_all_object_names()
        return find_matching_objects(query, all_names)
    
    def get_visibility(self, node) -> bool:
        """Get visibility of a node."""
        if not node:
            return False
        display_node = node.GetDisplayNode()
        if display_node:
            return display_node.GetVisibility()
        return True
    
    def get_opacity(self, node) -> Optional[float]:
        """Get opacity of a node."""
        if not node:
            return None
        display_node = node.GetDisplayNode()
        if display_node and hasattr(display_node, 'GetOpacity'):
            return display_node.GetOpacity()
        return None
    
    def set_visibility(self, node, visible: bool) -> bool:
        """Set visibility of a node."""
        if not node:
            return False
        display_node = node.GetDisplayNode()
        if display_node:
            display_node.SetVisibility(visible)
            return True
        return False
    
    def set_opacity(self, node, opacity: float) -> bool:
        """Set opacity of a node."""
        if not node:
            return False
        display_node = node.GetDisplayNode()
        if display_node and hasattr(display_node, 'SetOpacity'):
            display_node.SetOpacity(opacity)
            return True
        return False
    
    def set_color(self, node, color: List[float]) -> bool:
        """Set color of a node."""
        if not node:
            return False
        display_node = node.GetDisplayNode()
        if display_node and hasattr(display_node, 'SetColor'):
            display_node.SetColor(color[0], color[1], color[2])
            return True
        return False
    
    def reset_display(self, node) -> bool:
        """Reset display properties of a node."""
        if not node:
            return False
        display_node = node.GetDisplayNode()
        if display_node:
            display_node.SetVisibility(True)
            if hasattr(display_node, 'SetOpacity'):
                display_node.SetOpacity(1.0)
            return True
        return False


_scene_manager_instance = None


def get_scene_manager() -> SceneManager:
    """Get the global scene manager instance."""
    global _scene_manager_instance
    if _scene_manager_instance is None:
        _scene_manager_instance = SceneManager()
    return _scene_manager_instance