"""Verification Layer - Verifies action execution results against Slicer scene state."""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from .scene_manager import get_scene_manager
from .schemas import Action
from .action_engine import ActionResult


@dataclass
class VerificationResult:
    """Result of a verification check."""
    action_type: str
    target: str
    expected: Any
    actual: Any
    passed: bool
    message: str


class Verifier:
    """Verifies that actions produced the expected scene state changes."""
    
    def __init__(self):
        self.scene_manager = get_scene_manager()
    
    def verify_action(self, action: Action, action_result: ActionResult) -> VerificationResult:
        """Verify a single action's result."""
        action_type = action.type
        
        if action_type == "SHOW":
            return self._verify_show(action, action_result)
        elif action_type == "HIDE":
            return self._verify_hide(action, action_result)
        elif action_type == "SHOW_ONLY":
            return self._verify_show_only(action, action_result)
        elif action_type == "SET_OPACITY":
            return self._verify_set_opacity(action, action_result)
        elif action_type == "SET_COLOR":
            return self._verify_set_color(action, action_result)
        elif action_type == "RESET_DISPLAY":
            return self._verify_reset_display(action, action_result)
        elif action_type == "ZOOM_TO":
            return self._verify_zoom_to(action, action_result)
        elif action_type in ["THREE_D_VIEW", "AXIAL_VIEW", "SAGITTAL_VIEW", "CORONAL_VIEW"]:
            return self._verify_view(action, action_result)
        else:
            return VerificationResult(
                action_type=action_type,
                target=getattr(action, 'target', 'N/A'),
                expected="N/A",
                actual="N/A",
                passed=True,
                message=f"No verification for {action_type}"
            )
    
    def _verify_show(self, action: Action, action_result: ActionResult) -> VerificationResult:
        target_name = action.target
        node = self.scene_manager.find_node_by_name(target_name)
        
        if not node:
            return VerificationResult(
                action_type="SHOW",
                target=target_name,
                expected="visible",
                actual="node not found",
                passed=False,
                message=f"SHOW verification failed: {target_name} not found in scene"
            )
        
        visible = self.scene_manager.get_visibility(node)
        
        return VerificationResult(
            action_type="SHOW",
            target=target_name,
            expected="visible",
            actual="visible" if visible else "hidden",
            passed=visible,
            message=f"✓ {target_name} is visible" if visible else f"✗ {target_name} is still hidden"
        )
    
    def _verify_hide(self, action: Action, action_result: ActionResult) -> VerificationResult:
        target_name = action.target
        node = self.scene_manager.find_node_by_name(target_name)
        
        if not node:
            return VerificationResult(
                action_type="HIDE",
                target=target_name,
                expected="hidden",
                actual="node not found",
                passed=False,
                message=f"HIDE verification failed: {target_name} not found in scene"
            )
        
        visible = self.scene_manager.get_visibility(node)
        
        return VerificationResult(
            action_type="HIDE",
            target=target_name,
            expected="hidden",
            actual="hidden" if not visible else "visible",
            passed=not visible,
            message=f"✓ {target_name} is hidden" if not visible else f"✗ {target_name} is still visible"
        )
    
    def _verify_show_only(self, action: Action, action_result: ActionResult) -> VerificationResult:
        target_names = action.targets
        all_models = self.scene_manager.get_models()
        all_segmentations = self.scene_manager.get_segmentations()
        all_volumes = self.scene_manager.get_volumes()
        
        all_objects = all_models + all_segmentations + all_volumes
        target_nodes = set()
        failed_targets = []
        
        for target_name in target_names:
            node = self.scene_manager.find_node_by_name(target_name)
            if not node:
                failed_targets.append(target_name)
                continue
            target_nodes.add(node)
        
        if failed_targets:
            return VerificationResult(
                action_type="SHOW_ONLY",
                target=", ".join(target_names),
                expected=f"only {', '.join(target_names)} visible",
                actual=f"targets not found: {failed_targets}",
                passed=False,
                message=f"SHOW_ONLY verification failed: targets not found: {failed_targets}"
            )
        
        hidden_count = 0
        visible_count = 0
        unexpected_visible = []
        
        for obj in all_objects:
            node = self.scene_manager.find_node_by_name(obj.name)
            if node:
                visible = self.scene_manager.get_visibility(node)
                if node in target_nodes:
                    if visible:
                        visible_count += 1
                    else:
                        unexpected_visible.append(obj.name)
                else:
                    if visible:
                        unexpected_visible.append(obj.name)
                    else:
                        hidden_count += 1
        
        all_targets_visible = visible_count == len(target_names)
        no_unexpected_visible = len(unexpected_visible) == 0
        passed = all_targets_visible and no_unexpected_visible
        
        message_parts = []
        if all_targets_visible:
            message_parts.append(f"✓ Targets visible: {', '.join(target_names)}")
        else:
            message_parts.append(f"✗ Some targets not visible")
        
        if no_unexpected_visible:
            message_parts.append(f"✓ No unexpected objects visible")
        else:
            message_parts.append(f"✗ Unexpected visible: {', '.join(unexpected_visible)}")
        
        return VerificationResult(
            action_type="SHOW_ONLY",
            target=", ".join(target_names),
            expected=f"only targets visible",
            actual=f"visible: {visible_count}/{len(target_names)} targets, {len(unexpected_visible)} unexpected",
            passed=passed,
            message="; ".join(message_parts)
        )
    
    def _verify_set_opacity(self, action: Action, action_result: ActionResult) -> VerificationResult:
        target_name = action.target
        expected_opacity = action.value
        node = self.scene_manager.find_node_by_name(target_name)
        
        if not node:
            return VerificationResult(
                action_type="SET_OPACITY",
                target=target_name,
                expected=str(expected_opacity),
                actual="node not found",
                passed=False,
                message=f"SET_OPACITY verification failed: {target_name} not found"
            )
        
        actual_opacity = self.scene_manager.get_opacity(node)
        
        if actual_opacity is None:
            return VerificationResult(
                action_type="SET_OPACITY",
                target=target_name,
                expected=str(expected_opacity),
                actual="no opacity property",
                passed=False,
                message=f"SET_OPACITY verification failed: {target_name} has no opacity"
            )
        
        tolerance = 0.05
        passed = abs(actual_opacity - expected_opacity) < tolerance
        
        return VerificationResult(
            action_type="SET_OPACITY",
            target=target_name,
            expected=str(expected_opacity),
            actual=str(actual_opacity),
            passed=passed,
            message=f"✓ {target_name} opacity = {actual_opacity}" if passed 
                   else f"✗ {target_name} opacity = {actual_opacity} (expected {expected_opacity})"
        )
    
    def _verify_set_color(self, action: Action, action_result: ActionResult) -> VerificationResult:
        target_name = action.target
        expected_color = action.color
        node = self.scene_manager.find_node_by_name(target_name)
        
        if not node:
            return VerificationResult(
                action_type="SET_COLOR",
                target=target_name,
                expected=str(expected_color),
                actual="node not found",
                passed=False,
                message=f"SET_COLOR verification failed: {target_name} not found"
            )
        
        display_node = node.GetDisplayNode()
        if not display_node or not hasattr(display_node, 'GetColor'):
            return VerificationResult(
                action_type="SET_COLOR",
                target=target_name,
                expected=str(expected_color),
                actual="no color property",
                passed=False,
                message=f"SET_COLOR verification failed: {target_name} has no color"
            )
        
        actual_color = list(display_node.GetColor())
        tolerance = 0.05
        
        passed = all(abs(a - e) < tolerance for a, e in zip(actual_color, expected_color))
        
        return VerificationResult(
            action_type="SET_COLOR",
            target=target_name,
            expected=str(expected_color),
            actual=str(actual_color),
            passed=passed,
            message=f"✓ {target_name} color = {actual_color}" if passed
                   else f"✗ {target_name} color = {actual_color} (expected {expected_color})"
        )
    
    def _verify_reset_display(self, action: Action, action_result: ActionResult) -> VerificationResult:
        target_name = action.target
        node = self.scene_manager.find_node_by_name(target_name)
        
        if not node:
            return VerificationResult(
                action_type="RESET_DISPLAY",
                target=target_name,
                expected="visible, opacity=1.0",
                actual="node not found",
                passed=False,
                message=f"RESET_DISPLAY verification failed: {target_name} not found"
            )
        
        visible = self.scene_manager.get_visibility(node)
        opacity = self.scene_manager.get_opacity(node)
        
        passed = visible and (opacity is None or abs(opacity - 1.0) < 0.05)
        
        return VerificationResult(
            action_type="RESET_DISPLAY",
            target=target_name,
            expected="visible, opacity=1.0",
            actual=f"visible={visible}, opacity={opacity}",
            passed=passed,
            message=f"✓ {target_name} display reset" if passed
                   else f"✗ {target_name} display not fully reset (visible={visible}, opacity={opacity})"
        )
    
    def _verify_zoom_to(self, action: Action, action_result: ActionResult) -> VerificationResult:
        target_name = action.target
        node = self.scene_manager.find_node_by_name(target_name)
        
        if not node:
            return VerificationResult(
                action_type="ZOOM_TO",
                target=target_name,
                expected="camera focused on target",
                actual="node not found",
                passed=False,
                message=f"ZOOM_TO verification failed: {target_name} not found"
            )
        
        return VerificationResult(
            action_type="ZOOM_TO",
            target=target_name,
            expected="camera focused on target",
            actual="executed (camera state not verifiable)",
            passed=True,
            message=f"✓ ZOOM_TO {target_name} executed"
        )
    
    def _verify_view(self, action: Action, action_result: ActionResult) -> VerificationResult:
        return VerificationResult(
            action_type=action.type,
            target="view",
            expected=action.type.replace("_", " "),
            actual="executed",
            passed=True,
            message=f"✓ View changed to {action.type.replace('_', ' ')}"
        )
    
    def verify_plan(self, plan_actions: List[Action], action_results: List[ActionResult]) -> List[VerificationResult]:
        """Verify all actions in a plan."""
        results = []
        for action, result in zip(plan_actions, action_results):
            if result.success:
                verification = self.verify_action(action, result)
                results.append(verification)
            else:
                results.append(VerificationResult(
                    action_type=action.type,
                    target=getattr(action, 'target', 'N/A'),
                    expected="success",
                    actual=f"failed: {result.message}",
                    passed=False,
                    message=f"✗ {action.type} failed: {result.message}"
                ))
        return results


_verifier_instance = None


def get_verifier() -> Verifier:
    """Get the global verifier instance."""
    global _verifier_instance
    if _verifier_instance is None:
        _verifier_instance = Verifier()
    return _verifier_instance