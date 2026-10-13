"""Slicer AI Copilot - Main module entry point for 3D Slicer."""

import os
import sys
import logging

# Ensure module directory is in sys.path so SlicerAICopilotLib can be imported
module_dir = os.path.dirname(os.path.abspath(__file__))
if module_dir not in sys.path:
    sys.path.insert(0, module_dir)

try:
    import slicer
    from slicer.ScriptedLoadableModule import *
    from slicer.util import VTKObservationMixin
    SLICER_AVAILABLE = True
except ImportError:
    SLICER_AVAILABLE = False
    ScriptedLoadableModule = object
    ScriptedLoadableModuleWidget = object
    ScriptedLoadableModuleLogic = object
    VTKObservationMixin = object

# Auto-install runtime dependencies inside Slicer environment
if SLICER_AVAILABLE:
    try:
        import openai
    except ImportError:
        try:
            import slicer.util
            slicer.util.pip_install("openai>=1.0.0")
        except Exception as e:
            logging.warning(f"Could not auto-install openai: {e}")

    try:
        import pydantic
    except ImportError:
        try:
            import slicer.util
            slicer.util.pip_install("pydantic>=2.0.0")
        except Exception as e:
            logging.warning(f"Could not auto-install pydantic: {e}")


class SlicerAICopilot(ScriptedLoadableModule):
    """Main module class for Slicer AI Copilot."""

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Slicer AI Copilot"
        self.parent.categories = ["Utilities", "AI"]
        self.parent.dependencies = []
        self.parent.contributors = ["Slicer AI Copilot Team"]
        self.parent.helpText = """
        <h3>Slicer AI Copilot</h3>
        Natural-language AI assistant for 3D Slicer.

        <p>Control Slicer through chat commands:</p>
        <ul>
        <li><b>Visibility:</b> "Show the tumor", "Hide the skin", "Show only the tumor and vessels"</li>
        <li><b>Display:</b> "Make the liver transparent", "Set tumor opacity to 80%", "Make the tumor red"</li>
        <li><b>Navigation:</b> "Zoom to the tumor", "Show axial view", "Switch to 3D"</li>
        <li><b>Scene queries:</b> "What is loaded?", "What structures are visible?"</li>
        <li><b>Case import:</b> Drag a patient folder to import DICOM, NIfTI, models</li>
        </ul>

        <p><b>Safety:</b> All actions are validated before execution and verified after.</p>
        """
        self.parent.acknowledgementText = """
        Slicer AI Copilot - Natural language control for 3D Slicer.
        Built for hackathon challenge N35: Verified natural-language automation of 3D Slicer.
        """

        # Set module icon if available
        icon_path = os.path.join(module_dir, "Resources", "Icons", "SlicerAICopilot.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(module_dir, "..", "SlicerAICopilot.png")
        if os.path.exists(icon_path):
            try:
                import qt
                self.parent.icon = qt.QIcon(icon_path)
            except Exception:
                pass

        # Register module in Slicer modules namespace
        if SLICER_AVAILABLE:
            slicer.modules.sliceraicopilot = self


class SlicerAICopilotWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Module widget - creates and manages the chat UI."""

    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)
        self.logic = None
        self.chat_widget = None

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        # Create logic
        self.logic = SlicerAICopilotLogic()

        # Create chat UI
        from SlicerAICopilotLib.chat_ui import create_chat_widget
        self.chat_widget = create_chat_widget(self.parent)

        # Add to layout
        layout = self.layout
        if layout is None and self.parent is not None:
            import qt
            layout = qt.QVBoxLayout(self.parent)
            self.parent.setLayout(layout)

        if layout is not None:
            layout.addWidget(self.chat_widget)

    def cleanup(self):
        self.removeObservers()
        if self.chat_widget:
            self.chat_widget.deleteLater()
            self.chat_widget = None

    def onSceneStartClose(self, caller, event):
        if self.chat_widget and hasattr(self.chat_widget, 'pending_plan'):
            self.chat_widget.pending_plan = None
        if self.chat_widget and hasattr(self.chat_widget, 'conversation'):
            self.chat_widget.conversation.clear()
            if hasattr(self.chat_widget, 'conversation_layout'):
                while self.chat_widget.conversation_layout.count():
                    item = self.chat_widget.conversation_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
            if hasattr(self.chat_widget, 'add_welcome_message'):
                self.chat_widget.add_welcome_message()
        if self.chat_widget and hasattr(self.chat_widget, 'set_state'):
            from SlicerAICopilotLib.chat_ui import UIState
            self.chat_widget.set_state(UIState.IDLE)

    def onSceneEndClose(self, caller, event):
        pass


class SlicerAICopilotLogic(ScriptedLoadableModuleLogic):
    """Module logic - coordinates all components."""

    def __init__(self):
        ScriptedLoadableModuleLogic.__init__(self)

        # Initialize core components
        from SlicerAICopilotLib.scene_manager import get_scene_manager
        from SlicerAICopilotLib.action_engine import get_action_engine
        from SlicerAICopilotLib.validator import get_validator
        from SlicerAICopilotLib.verification import get_verifier
        from SlicerAICopilotLib.llm_client import get_llm_client
        from SlicerAICopilotLib.file_manager import get_file_manager

        self.scene_manager = get_scene_manager()
        self.action_engine = get_action_engine()
        self.validator = get_validator()
        self.verifier = get_verifier()
        self.llm_client = get_llm_client()
        self.file_manager = get_file_manager()

    def get_scene_summary(self):
        """Get current scene summary."""
        return self.scene_manager.get_scene_summary()

    def execute_action_plan(self, plan):
        """Execute and verify an action plan."""
        results = self.action_engine.execute_plan(plan)
        verification = self.verifier.verify_plan(plan.actions, results)
        return results, verification

    def _resolve_prompt_path(self, filename: str) -> str:
        candidates = [
            os.path.join(module_dir, "Resources", "prompts", filename),
            os.path.join(module_dir, "prompts", filename),
            os.path.join(module_dir, "..", "prompts", filename),
            os.path.join(module_dir, "SlicerAICopilotLib", "prompts", filename),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return ""

    def load_prompt(self, filename: str) -> str:
        """Load prompt from file."""
        resolved = self._resolve_prompt_path(filename)
        if resolved and os.path.exists(resolved):
            try:
                with open(resolved, 'r') as f:
                    return f.read()
            except Exception:
                return ""
        return ""

    def _resolve_knowledge_path(self, filename: str) -> str:
        candidates = [
            os.path.join(module_dir, "Resources", "knowledge", filename),
            os.path.join(module_dir, "knowledge", filename),
            os.path.join(module_dir, "..", "knowledge", filename),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return ""

    def _load_examples(self) -> list:
        """Load few-shot examples from slicer_examples.json for LLM context."""
        import json
        resolved = self._resolve_knowledge_path("slicer_examples.json")
        if not resolved:
            return []
        try:
            with open(resolved, 'r') as f:
                data = json.load(f)
            examples = data.get("examples", [])
            messages = []
            for ex in examples[:8]:
                messages.append({"role": "user", "content": ex["user"]})
                messages.append({"role": "assistant", "content": json.dumps(ex["response"])})
            return messages
        except Exception:
            return []

    def process_user_command(self, text: str):
        """Process a natural language command.

        Returns:
            Tuple of (plan, results, verification) where:
            - plan: ActionPlan or None if LLM failed
            - results: list of ActionResult or list of error strings
            - verification: list of VerificationResult or None
        """
        from SlicerAICopilotLib.schemas import ActionPlan
        from SlicerAICopilotLib.utils import format_scene_summary
        import json

        scene_summary = self.scene_manager.get_scene_summary()
        scene_text = format_scene_summary({
            "volumes": [o.model_dump() for o in scene_summary.volumes],
            "models": [o.model_dump() for o in scene_summary.models],
            "segmentations": [o.model_dump() for o in scene_summary.segmentations],
            "markups": [o.model_dump() for o in scene_summary.markups],
            "transforms": [o.model_dump() for o in scene_summary.transforms],
        })

        system_prompt = self.load_prompt("system_prompt.txt")
        action_prompt = self.load_prompt("action_prompt.txt")

        if not system_prompt:
            system_prompt = "You are Slicer AI Copilot, an AI assistant for 3D Slicer. Return valid JSON only."
        if not action_prompt:
            action_prompt = 'Return JSON: {"version":"1.0","reply":"...","actions":[]}'

        examples = self._load_examples()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"Current Slicer scene:\n{scene_text}"},
        ]
        messages.extend(examples)
        messages.append({"role": "system", "content": action_prompt})
        messages.append({"role": "user", "content": text})

        response = self.llm_client.complete(
            messages,
            temperature=0.1,
            max_tokens=2048,
            response_format={"type": "json_object"}
        )

        if not response.content:
            return None, ["Empty response from LLM"], None

        try:
            data = json.loads(response.content)
            plan = ActionPlan.model_validate(data)
        except Exception as e:
            return None, [f"Failed to parse LLM response: {e}"], None

        valid, errors = self.validator.validate_plan(plan)
        if not valid:
            return plan, errors, None

        results = self.action_engine.execute_plan(plan)
        verification = self.verifier.verify_plan(plan.actions, results)

        return plan, results, verification

    def scan_folder(self, folder_path: str):
        """Scan folder for supported files."""
        return self.file_manager.scan_folder(folder_path)

    def import_case(self, scan_result: dict, selections: dict):
        """Import selected files from scan result."""
        return self.file_manager.import_case(scan_result, selections)


# Export for Slicer module discovery
__all__ = ['SlicerAICopilot', 'SlicerAICopilotWidget', 'SlicerAICopilotLogic']
