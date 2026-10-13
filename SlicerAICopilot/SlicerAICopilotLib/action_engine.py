"""Action Engine - Executes validated actions on the Slicer scene."""

try:
    import slicer
    from slicer import vtkMRMLScene, vtkMRMLScalarVolumeNode, vtkMRMLModelNode
    from slicer import vtkMRMLSegmentationNode, vtkMRMLViewNode
    SLICER_AVAILABLE = True
except ImportError:
    SLICER_AVAILABLE = False
    slicer = None

from typing import Dict, List, Optional, Any, Tuple
from .schemas import (
    Action, ActionPlan, ALLOWED_ACTIONS, ACTION_CLASSES,
    ShowAction, HideAction, ShowOnlyAction, SetOpacityAction,
    SetColorAction, ResetDisplayAction, ResetViewAction,
    ZoomToAction, ViewAction, ListObjectsAction, ListVisibleObjectsAction,
    OpenFolderAction, ImportDicomAction, LoadVolumeAction,
    LoadModelAction, LoadSegmentationAction
)
from .scene_manager import get_scene_manager
from .file_manager import get_file_manager
from .utils import format_scene_summary


class ActionResult:
    """Result of an action execution."""
    def __init__(self, success: bool, message: str, data: Any = None):
        self.success = success
        self.message = message
        self.data = data


class ActionEngine:
    """Executes validated actions on the Slicer scene."""
    
    def __init__(self):
        self.scene_manager = get_scene_manager()
        self.file_manager = get_file_manager()
    
    def execute_action(self, action: Action) -> ActionResult:
        """Execute a single validated action."""
        action_type = action.type
        
        if action_type == "SHOW":
            return self._execute_show(action)
        elif action_type == "HIDE":
            return self._execute_hide(action)
        elif action_type == "SHOW_ONLY":
            return self._execute_show_only(action)
        elif action_type == "SET_OPACITY":
            return self._execute_set_opacity(action)
        elif action_type == "SET_COLOR":
            return self._execute_set_color(action)
        elif action_type == "RESET_DISPLAY":
            return self._execute_reset_display(action)
        elif action_type == "RESET_VIEW":
            return self._execute_reset_view(action)
        elif action_type == "ZOOM_TO":
            return self._execute_zoom_to(action)
        elif action_type in ["THREE_D_VIEW", "AXIAL_VIEW", "SAGITTAL_VIEW", "CORONAL_VIEW"]:
            return self._execute_view(action)
        elif action_type == "LIST_OBJECTS":
            return self._execute_list_objects(action)
        elif action_type == "LIST_VISIBLE_OBJECTS":
            return self._execute_list_visible_objects(action)
        elif action_type == "OPEN_FOLDER":
            return self._execute_open_folder(action)
        elif action_type == "IMPORT_DICOM":
            return self._execute_import_dicom(action)
        elif action_type == "LOAD_VOLUME":
            return self._execute_load_volume(action)
        elif action_type == "LOAD_MODEL":
            return self._execute_load_model(action)
        elif action_type == "LOAD_SEGMENTATION":
            return self._execute_load_segmentation(action)
        else:
            return ActionResult(False, f"Unknown action type: {action_type}")
    
    def execute_plan(self, plan: ActionPlan) -> List[ActionResult]:
        """Execute a full action plan."""
        results = []
        for action in plan.actions:
            result = self.execute_action(action)
            results.append(result)
            if not result.success:
                break
        return results
    
    def _execute_show(self, action: ShowAction) -> ActionResult:
        target_name = action.target
        node = self.scene_manager.find_node_by_name(target_name)
        
        if not node:
            matches = self.scene_manager.find_matching_targets(target_name)
            if len(matches) == 1:
                node = self.scene_manager.find_node_by_name(matches[0])
            elif len(matches) > 1:
                return ActionResult(False, f"Ambiguous target '{target_name}'. Matches: {matches}")
            else:
                return ActionResult(False, f"Object '{target_name}' not found in scene")
        
        success = self.scene_manager.set_visibility(node, True)
        if success:
            return ActionResult(True, f"Shown: {target_name}")
        return ActionResult(False, f"Failed to show: {target_name}")
    
    def _execute_hide(self, action: HideAction) -> ActionResult:
        target_name = action.target
        node = self.scene_manager.find_node_by_name(target_name)
        
        if not node:
            matches = self.scene_manager.find_matching_targets(target_name)
            if len(matches) == 1:
                node = self.scene_manager.find_node_by_name(matches[0])
            elif len(matches) > 1:
                return ActionResult(False, f"Ambiguous target '{target_name}'. Matches: {matches}")
            else:
                return ActionResult(False, f"Object '{target_name}' not found in scene")
        
        success = self.scene_manager.set_visibility(node, False)
        if success:
            return ActionResult(True, f"Hidden: {target_name}")
        return ActionResult(False, f"Failed to hide: {target_name}")
    
    def _execute_show_only(self, action: ShowOnlyAction) -> ActionResult:
        target_names = action.targets
        all_models = self.scene_manager.get_models()
        all_segmentations = self.scene_manager.get_segmentations()
        all_volumes = self.scene_manager.get_volumes()
        
        all_objects = all_models + all_segmentations + all_volumes
        target_nodes = []
        
        for target_name in target_names:
            node = self.scene_manager.find_node_by_name(target_name)
            if not node:
                matches = self.scene_manager.find_matching_targets(target_name)
                if len(matches) == 1:
                    node = self.scene_manager.find_node_by_name(matches[0])
                elif len(matches) > 1:
                    return ActionResult(False, f"Ambiguous target '{target_name}'. Matches: {matches}")
                else:
                    return ActionResult(False, f"Object '{target_name}' not found in scene")
            target_nodes.append(node)
        
        for obj in all_objects:
            node = self.scene_manager.find_node_by_name(obj.name)
            if node and node not in target_nodes:
                self.scene_manager.set_visibility(node, False)
        
        for node in target_nodes:
            self.scene_manager.set_visibility(node, True)
        
        return ActionResult(True, f"Showing only: {', '.join(target_names)}")
    
    def _execute_set_opacity(self, action: SetOpacityAction) -> ActionResult:
        target_name = action.target
        node = self.scene_manager.find_node_by_name(target_name)
        
        if not node:
            matches = self.scene_manager.find_matching_targets(target_name)
            if len(matches) == 1:
                node = self.scene_manager.find_node_by_name(matches[0])
            elif len(matches) > 1:
                return ActionResult(False, f"Ambiguous target '{target_name}'. Matches: {matches}")
            else:
                return ActionResult(False, f"Object '{target_name}' not found in scene")
        
        success = self.scene_manager.set_opacity(node, action.value)
        if success:
            return ActionResult(True, f"Set opacity of {target_name} to {action.value}")
        return ActionResult(False, f"Failed to set opacity: {target_name}")
    
    def _execute_set_color(self, action: SetColorAction) -> ActionResult:
        target_name = action.target
        node = self.scene_manager.find_node_by_name(target_name)
        
        if not node:
            matches = self.scene_manager.find_matching_targets(target_name)
            if len(matches) == 1:
                node = self.scene_manager.find_node_by_name(matches[0])
            elif len(matches) > 1:
                return ActionResult(False, f"Ambiguous target '{target_name}'. Matches: {matches}")
            else:
                return ActionResult(False, f"Object '{target_name}' not found in scene")
        
        success = self.scene_manager.set_color(node, action.color)
        if success:
            return ActionResult(True, f"Set color of {target_name} to {action.color}")
        return ActionResult(False, f"Failed to set color: {target_name}")
    
    def _execute_reset_display(self, action: ResetDisplayAction) -> ActionResult:
        target_name = action.target
        node = self.scene_manager.find_node_by_name(target_name)
        
        if not node:
            matches = self.scene_manager.find_matching_targets(target_name)
            if len(matches) == 1:
                node = self.scene_manager.find_node_by_name(matches[0])
            elif len(matches) > 1:
                return ActionResult(False, f"Ambiguous target '{target_name}'. Matches: {matches}")
            else:
                return ActionResult(False, f"Object '{target_name}' not found in scene")
        
        success = self.scene_manager.reset_display(node)
        if success:
            return ActionResult(True, f"Reset display: {target_name}")
        return ActionResult(False, f"Failed to reset display: {target_name}")
    
    def _execute_reset_view(self, action: ResetViewAction) -> ActionResult:
        if not SLICER_AVAILABLE:
            return ActionResult(False, "Slicer not available")
        
        layout_manager = slicer.app.layoutManager()
        if layout_manager:
            for i in range(layout_manager.threeDViewCount):
                view = layout_manager.threeDWidget(i).threeDView()
                view.resetFocalPoint()
            return ActionResult(True, "Reset 3D view")
        return ActionResult(False, "No 3D view found")
    
    def _execute_zoom_to(self, action: ZoomToAction) -> ActionResult:
        target_name = action.target
        node = self.scene_manager.find_node_by_name(target_name)
        
        if not node:
            matches = self.scene_manager.find_matching_targets(target_name)
            if len(matches) == 1:
                node = self.scene_manager.find_node_by_name(matches[0])
            elif len(matches) > 1:
                return ActionResult(False, f"Ambiguous target '{target_name}'. Matches: {matches}")
            else:
                return ActionResult(False, f"Object '{target_name}' not found in scene")
        
        if not SLICER_AVAILABLE:
            return ActionResult(False, "Slicer not available")
        
        layout_manager = slicer.app.layoutManager()
        if not layout_manager:
            return ActionResult(False, "No layout manager")
        
        try:
            import vtk
            bounds = [0.0] * 6
            node.GetRASBounds(bounds)
            center = [
                (bounds[0] + bounds[1]) / 2.0,
                (bounds[2] + bounds[3]) / 2.0,
                (bounds[4] + bounds[5]) / 2.0,
            ]
            focal_point = vtk.vtkVector3d(center)
            
            for i in range(layout_manager.threeDViewCount):
                three_d_widget = layout_manager.threeDWidget(i)
                three_d_view = three_d_widget.threeDView()
                render_window = three_d_view.renderWindow()
                if not render_window:
                    continue
                renderer = render_window.GetRenderers().GetFirstRenderer()
                if not renderer:
                    continue
                camera = renderer.GetActiveCamera()
                if camera:
                    camera.SetFocalPoint(focal_point)
                    renderer.ResetCamera()
                    three_d_view.renderWindow().Render()
            
            return ActionResult(True, f"Zoomed to: {target_name}")
        except Exception as e:
            return ActionResult(False, f"Zoom failed: {str(e)}")
    
    def _execute_view(self, action: ViewAction) -> ActionResult:
        if not SLICER_AVAILABLE:
            return ActionResult(False, "Slicer not available")
        
        layout_manager = slicer.app.layoutManager()
        if not layout_manager:
            return ActionResult(False, "No layout manager")
        
        try:
            view_type = action.type
            if view_type == "THREE_D_VIEW":
                layout_manager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
                return ActionResult(True, "Switched to 3D view")
            elif view_type == "AXIAL_VIEW":
                layout_manager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpSliceView)
                self._set_slice_view_orientation(layout_manager, "axial")
                return ActionResult(True, "Switched to axial view")
            elif view_type == "SAGITTAL_VIEW":
                layout_manager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpSliceView)
                self._set_slice_view_orientation(layout_manager, "sagittal")
                return ActionResult(True, "Switched to sagittal view")
            elif view_type == "CORONAL_VIEW":
                layout_manager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpSliceView)
                self._set_slice_view_orientation(layout_manager, "coronal")
                return ActionResult(True, "Switched to coronal view")
            else:
                return ActionResult(False, f"Unknown view type: {view_type}")
        except Exception as e:
            return ActionResult(False, f"View switch failed: {str(e)}")
    
    def _set_slice_view_orientation(self, layout_manager, orientation: str) -> None:
        """Set the orientation of slice views."""
        orientation_map = {
            "axial": "Axial",
            "sagittal": "Sagittal",
            "coronal": "Coronal",
        }
        orient_name = orientation_map.get(orientation)
        if not orient_name:
            return
        
        for i in range(layout_manager.sliceViewCount):
            slice_widget = layout_manager.sliceWidget(i)
            if slice_widget:
                slice_view = slice_widget.sliceView()
                if slice_view:
                    slice_logic = slice_view.mrmlSliceCompositeNode()
                    if slice_logic:
                        slice_logic.SetSliceOrientationPreset(orient_name)
    
    def _execute_list_objects(self, action: ListObjectsAction) -> ActionResult:
        summary = self.scene_manager.get_scene_summary()
        formatted = format_scene_summary({
            "volumes": [o.model_dump() for o in summary.volumes],
            "models": [o.model_dump() for o in summary.models],
            "segmentations": [o.model_dump() for o in summary.segmentations],
            "markups": [o.model_dump() for o in summary.markups],
            "transforms": [o.model_dump() for o in summary.transforms],
        })
        return ActionResult(True, formatted, summary.model_dump())
    
    def _execute_list_visible_objects(self, action: ListVisibleObjectsAction) -> ActionResult:
        summary = self.scene_manager.get_scene_summary()
        visible_objects = []
        
        for category in [summary.volumes, summary.models, summary.segmentations, summary.markups, summary.transforms]:
            for obj in category:
                if obj.visible:
                    visible_objects.append(obj.name)
        
        message = "Visible objects:\n" + "\n".join(f"  - {name}" for name in visible_objects) if visible_objects else "No visible objects"
        return ActionResult(True, message, {"visible": visible_objects})
    
    def _execute_open_folder(self, action: OpenFolderAction) -> ActionResult:
        result = self.file_manager.scan_folder(action.path)
        return ActionResult(True, f"Scanned folder: {action.path}", result)
    
    def _execute_import_dicom(self, action: ImportDicomAction) -> ActionResult:
        if not SLICER_AVAILABLE:
            return ActionResult(False, "Slicer not available")
        
        try:
            import slicer.util
            loaded_nodes = slicer.util.loadDICOM(action.path)
            if loaded_nodes:
                return ActionResult(True, f"Imported DICOM from: {action.path}", {"nodes": loaded_nodes})
            return ActionResult(False, f"No DICOM data loaded from: {action.path}")
        except Exception as e:
            return ActionResult(False, f"DICOM import failed: {str(e)}")
    
    def _execute_load_volume(self, action: LoadVolumeAction) -> ActionResult:
        if not SLICER_AVAILABLE:
            return ActionResult(False, "Slicer not available")
        
        try:
            import slicer.util
            node = slicer.util.loadVolume(action.path)
            if node:
                return ActionResult(True, f"Loaded volume: {node.GetName()}", {"node": node.GetName()})
            return ActionResult(False, f"Failed to load volume: {action.path}")
        except Exception as e:
            return ActionResult(False, f"Volume load failed: {str(e)}")
    
    def _execute_load_model(self, action: LoadModelAction) -> ActionResult:
        if not SLICER_AVAILABLE:
            return ActionResult(False, "Slicer not available")
        
        try:
            import slicer.util
            node = slicer.util.loadModel(action.path)
            if node:
                return ActionResult(True, f"Loaded model: {node.GetName()}", {"node": node.GetName()})
            return ActionResult(False, f"Failed to load model: {action.path}")
        except Exception as e:
            return ActionResult(False, f"Model load failed: {str(e)}")
    
    def _execute_load_segmentation(self, action: LoadSegmentationAction) -> ActionResult:
        if not SLICER_AVAILABLE:
            return ActionResult(False, "Slicer not available")
        
        try:
            import slicer.util
            node = slicer.util.loadSegmentation(action.path)
            if node:
                return ActionResult(True, f"Loaded segmentation: {node.GetName()}", {"node": node.GetName()})
            return ActionResult(False, f"Failed to load segmentation: {action.path}")
        except Exception as e:
            return ActionResult(False, f"Segmentation load failed: {str(e)}")


_action_engine_instance = None


def get_action_engine() -> ActionEngine:
    """Get the global action engine instance."""
    global _action_engine_instance
    if _action_engine_instance is None:
        _action_engine_instance = ActionEngine()
    return _action_engine_instance