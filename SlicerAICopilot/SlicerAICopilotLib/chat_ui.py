"""Chat UI - Main Qt widget for Slicer AI Copilot panel."""

try:
    from slicer.util import VTKObservationMixin
    from slicer import qSlicerModuleWidget, qSlicerAbstractModule
    from slicer import app
    SLICER_AVAILABLE = True
except ImportError:
    SLICER_AVAILABLE = False
    VTKObservationMixin = object
    qSlicerModuleWidget = object
    qSlicerAbstractModule = object

try:
    import qt
    from qt import (
        QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton,
        QLabel, QFrame, QScrollArea, QSizePolicy, QApplication, QMessageBox,
        QFileDialog, QProgressBar, QSplitter, QTextBrowser, QCheckBox,
        QFont, QColor, QPalette, QTextCursor, QTextCharFormat, QIcon,
        Qt, QUrl, QMimeData, QSize, QTimer, QComboBox
    )
    QT_AVAILABLE = True
except ImportError:
    try:
        from PythonQt import QtCore, QtGui, QtWidgets
        from PythonQt.QtCore import Qt, QUrl, QMimeData, QSize, QTimer
        from PythonQt.QtGui import QFont, QColor, QPalette, QTextCursor, QTextCharFormat, QIcon
        from PythonQt.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QPushButton,
            QLabel, QFrame, QScrollArea, QSizePolicy, QApplication, QMessageBox,
            QFileDialog, QProgressBar, QSplitter, QTextBrowser, QCheckBox,
            QComboBox
        )
        QT_AVAILABLE = True
    except ImportError:
        QT_AVAILABLE = False


class Signal:
    """Callback-based signal implementation compatible with PythonQt and headless tests."""
    def __init__(self, *arg_types):
        self._slots = []

    def connect(self, slot):
        if slot not in self._slots:
            self._slots.append(slot)

    def disconnect(self, slot=None):
        if slot is None:
            self._slots.clear()
        elif slot in self._slots:
            self._slots.remove(slot)

    def emit(self, *args, **kwargs):
        for slot in list(self._slots):
            slot(*args, **kwargs)

import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from .schemas import ActionPlan, Action
from .scene_manager import get_scene_manager
from .action_engine import get_action_engine, ActionResult
from .validator import get_validator, ValidationError
from .verification import get_verifier, VerificationResult
from .llm_client import get_llm_client, LLMResponse, PROVIDER_CONFIGS
from .file_manager import get_file_manager
from .utils import format_scene_summary


logger = logging.getLogger(__name__)


class UIState(Enum):
    IDLE = "IDLE"
    THINKING = "THINKING"
    PROPOSING = "PROPOSING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


@dataclass
class ChatMessage:
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime
    action_plan: Optional[ActionPlan] = None
    verification_results: Optional[List[VerificationResult]] = None
    state: UIState = UIState.IDLE


class StatusIndicator(QWidget):
    """Colored status indicator with label."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        self.dot = QLabel("●")
        self.dot.setFont(QFont("Arial", 14))
        self.label = QLabel("Ready")
        self.label.setFont(QFont("Arial", 10))
        
        layout.addWidget(self.dot)
        layout.addWidget(self.label)
        layout.addStretch()
        
        self.set_state(UIState.IDLE)
    
    def set_state(self, state: UIState):
        colors = {
            UIState.IDLE: "#666666",
            UIState.THINKING: "#FFA500",
            UIState.PROPOSING: "#2196F3",
            UIState.EXECUTING: "#9C27B0",
            UIState.VERIFYING: "#00BCD4",
            UIState.SUCCESS: "#4CAF50",
            UIState.ERROR: "#F44336",
        }
        
        labels = {
            UIState.IDLE: "Ready",
            UIState.THINKING: "Thinking...",
            UIState.PROPOSING: "Proposing actions...",
            UIState.EXECUTING: "Executing...",
            UIState.VERIFYING: "Verifying...",
            UIState.SUCCESS: "Done",
            UIState.ERROR: "Error",
        }
        
        color = colors.get(state, "#666666")
        self.dot.setStyleSheet(f"color: {color};")
        self.label.setText(labels.get(state, "Ready"))


class MessageWidget(QWidget):
    """Single chat message widget."""
    
    def __init__(self, message: ChatMessage, parent=None):
        super().__init__(parent)
        self.message = message
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)
        
        # Header with role and timestamp
        header = QHBoxLayout()
        role_label = QLabel(self.message.role.capitalize())
        role_label.setFont(QFont("Arial", 9, QFont.Bold))
        
        time_str = self.message.timestamp.strftime("%H:%M:%S")
        time_label = QLabel(time_str)
        time_label.setFont(QFont("Arial", 8))
        time_label.setStyleSheet("color: #888;")
        
        header.addWidget(role_label)
        header.addWidget(time_label)
        header.addStretch()
        layout.addLayout(header)
        
        # Content
        if self.message.role == "user":
            content_label = QLabel(self.message.content)
            content_label.setWordWrap(True)
            content_label.setStyleSheet("""
                QLabel {
                    background-color: #E3F2FD;
                    border-radius: 8px;
                    padding: 8px 12px;
                    color: #1565C0;
                }
            """)
            content_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
            layout.addWidget(content_label)
        
        elif self.message.role == "assistant":
            if self.message.action_plan:
                self.add_action_plan(layout)
            
            if self.message.verification_results:
                self.add_verification(layout)
            
            if self.message.content and not self.message.action_plan:
                content_label = QLabel(self.message.content)
                content_label.setWordWrap(True)
                content_label.setStyleSheet("""
                    QLabel {
                        background-color: #E8F5E9;
                        border-radius: 8px;
                        padding: 8px 12px;
                        color: #2E7D32;
                    }
                """)
                layout.addWidget(content_label)
        
        elif self.message.role == "system":
            content_label = QLabel(self.message.content)
            content_label.setWordWrap(True)
            content_label.setStyleSheet("""
                QLabel {
                    background-color: #FFF3E0;
                    border-radius: 8px;
                    padding: 8px 12px;
                    color: #E65100;
                    font-style: italic;
                }
            """)
            layout.addWidget(content_label)
    
    def add_action_plan(self, layout: QVBoxLayout):
        plan = self.message.action_plan
        
        plan_frame = QFrame()
        plan_frame.setFrameStyle(QFrame.StyledPanel)
        plan_frame.setStyleSheet("""
            QFrame {
                background-color: #F3E5F5;
                border-radius: 8px;
                border: 1px solid #CE93D8;
            }
        """)
        plan_layout = QVBoxLayout(plan_frame)
        
        reply_label = QLabel(f"🤖 {plan.reply}")
        reply_label.setWordWrap(True)
        reply_label.setFont(QFont("Arial", 9))
        plan_layout.addWidget(reply_label)
        
        if plan.actions:
            actions_label = QLabel("Proposed actions:")
            actions_label.setFont(QFont("Arial", 9, QFont.Bold))
            plan_layout.addWidget(actions_label)
            
            for action in plan.actions:
                action_text = self.format_action(action)
                action_label = QLabel(f"  → {action_text}")
                action_label.setFont(QFont("Monospace", 8))
                action_label.setStyleSheet("color: #7B1FA2;")
                plan_layout.addWidget(action_label)
        
        layout.addWidget(plan_frame)
    
    def add_verification(self, layout: QVBoxLayout):
        verify_frame = QFrame()
        verify_frame.setFrameStyle(QFrame.StyledPanel)
        verify_frame.setStyleSheet("""
            QFrame {
                background-color: #E8F5E9;
                border-radius: 8px;
                border: 1px solid #A5D6A7;
            }
        """)
        verify_layout = QVBoxLayout(verify_frame)
        
        title = QLabel("Verification Results")
        title.setFont(QFont("Arial", 9, QFont.Bold))
        verify_layout.addWidget(title)
        
        for vr in self.message.verification_results:
            status = "✓" if vr.passed else "✗"
            color = "#4CAF50" if vr.passed else "#F44336"
            vr_label = QLabel(f"  {status} {vr.message}")
            vr_label.setFont(QFont("Arial", 8))
            vr_label.setStyleSheet(f"color: {color};")
            verify_layout.addWidget(vr_label)
        
        layout.addWidget(verify_frame)
    
    def format_action(self, action: Action) -> str:
        if action.type in ["SHOW", "HIDE", "SET_OPACITY", "SET_COLOR", "RESET_DISPLAY", "ZOOM_TO"]:
            return f"{action.type} {action.target}" + (f" = {action.value}" if hasattr(action, 'value') and action.value is not None else "")
        elif action.type == "SHOW_ONLY":
            return f"{action.type} {', '.join(action.targets)}"
        else:
            return action.type


class DropZone(QLabel):
    """Drag-and-drop zone for folder import."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder_dropped = Signal(str)
        self.files_dropped = Signal(list)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(100)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #BBB;
                border-radius: 8px;
                background-color: #FAFAFA;
                color: #888;
                font-size: 12px;
            }
            QLabel[dragActive="true"] {
                border-color: #2196F3;
                background-color: #E3F2FD;
                color: #2196F3;
            }
        """)
        self.setText("Drag case folder or files here\nor click to browse")
        self.setProperty("dragActive", False)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
    
    def dragLeaveEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
    
    def dropEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        
        urls = event.mimeData().urls()
        if not urls:
            return
        
        paths = []
        for url in urls:
            try:
                path = url.toLocalFile()
                if path:
                    paths.append(str(path))
            except Exception:
                continue
        
        if not paths:
            return
        
        folders = [p for p in paths if os.path.isdir(p)]
        files = [p for p in paths if os.path.isfile(p)]
        
        if folders and len(folders) == 1:
            self.folder_dropped.emit(folders[0])
        elif folders and len(folders) > 1:
            self.folder_dropped.emit(json.dumps(folders))
        elif files:
            self.files_dropped.emit(files)
        
        if folders and files:
            self.files_dropped.emit(files)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            folder = QFileDialog.getExistingDirectory(self, "Select Case Folder")
            if folder:
                self.folder_dropped.emit(folder)


class CaseImportDialog(QWidget):
    """Dialog for selecting files to import from scanned folder."""
    
    def __init__(self, scan_result: Dict, parent=None):
        super().__init__(parent)
        self.import_requested = Signal(dict)
        self.scan_result = scan_result
        self.setWindowTitle("Import Case Data")
        self.setMinimumSize(500, 400)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        title = QLabel("Detected Files")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title)
        
        # Scroll area for file lists
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        self.checkboxes = {}
        
        categories = [
            ("dicom_series_groups", "DICOM Series", "dicom_series"),
            ("nifti_files", "NIfTI Files", "nifti_files"),
            ("nrrd_files", "NRRD Files", "nrrd_files"),
            ("model_files", "Model Files (.vtk, .stl, .obj, .ply)", "model_files"),
        ]
        
        has_files = False
        for key, label, cat_key in categories:
            files = self.scan_result.get(key, [])
            if files:
                has_files = True
                group = QWidget()
                group_layout = QVBoxLayout(group)
                
                cat_label = QLabel(f"{label} ({len(files)})")
                cat_label.setFont(QFont("Arial", 10, QFont.Bold))
                group_layout.addWidget(cat_label)
                
                for i, f in enumerate(files):
                    cb = QCheckBox(os.path.basename(f))
                    cb.setChecked(True)
                    cb.setProperty("category", cat_key)
                    cb.setProperty("index", i)
                    group_layout.addWidget(cb)
                    self.checkboxes[f"{cat_key}_{i}"] = cb
                
                scroll_layout.addWidget(group)
        
        other_files = self.scan_result.get("other_files", [])
        if other_files:
            has_files = True
            group = QWidget()
            group_layout = QVBoxLayout(group)
            cat_label = QLabel(f"Other Files ({len(other_files)}) - not imported")
            cat_label.setFont(QFont("Arial", 10, QFont.Bold))
            cat_label.setStyleSheet("color: #888;")
            group_layout.addWidget(cat_label)
            for f in other_files[:10]:
                lbl = QLabel(f"  {os.path.basename(f)}")
                lbl.setFont(QFont("Arial", 9))
                lbl.setStyleSheet("color: #888;")
                group_layout.addWidget(lbl)
            if len(other_files) > 10:
                lbl = QLabel(f"  ... and {len(other_files) - 10} more")
                lbl.setStyleSheet("color: #888;")
                group_layout.addWidget(lbl)
            scroll_layout.addWidget(group)
        
        if not has_files:
            no_files_label = QLabel("No supported files found in this folder.\n\nSupported formats:\n  - DICOM (.dcm)\n  - NIfTI (.nii, .nii.gz)\n  - NRRD (.nrrd)\n  - Models (.vtk, .stl, .obj, .ply)")
            no_files_label.setStyleSheet("color: #888; padding: 20px;")
            no_files_label.setWordWrap(True)
            scroll_layout.addWidget(no_files_label)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        
        import_btn = QPushButton("Import Selected")
        import_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px 24px; }")
        import_btn.clicked.connect(self.on_import)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(import_btn)
        layout.addLayout(btn_layout)
    
    def on_import(self):
        selections = {}
        for key, cb in self.checkboxes.items():
            if cb.isChecked():
                cat = cb.property("category")
                idx = cb.property("index")
                if cat not in selections:
                    selections[cat] = []
                selections[cat].append(idx)
        
        self.import_requested.emit(selections)
        self.close()


class SlicerAICopilotWidget(QWidget, VTKObservationMixin):
    """Main widget for Slicer AI Copilot module."""
    
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)
        
        self.scene_manager = get_scene_manager()
        self.action_engine = get_action_engine()
        self.validator = get_validator()
        self.verifier = get_verifier()
        self.llm_client = get_llm_client()
        self.file_manager = get_file_manager()
        
        self.conversation: List[ChatMessage] = []
        self.current_state = UIState.IDLE
        self.pending_plan: Optional[ActionPlan] = None
        
        self.init_ui()
        self.load_system_prompt()
        self.load_saved_settings()
        self.add_welcome_message()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setFixedHeight(48)
        header.setStyleSheet("background-color: #1976D2; color: white;")
        header_layout = QHBoxLayout(header)
        
        title = QLabel("Slicer AI Copilot")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        title.setStyleSheet("color: white;")
        
        self.status_indicator = StatusIndicator()
        
        self.settings_button = QPushButton("Settings")
        self.settings_button.setFixedSize(70, 30)
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255,255,255,0.2);
                color: white;
                border: 1px solid rgba(255,255,255,0.4);
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: rgba(255,255,255,0.3); }
        """)
        self.settings_button.clicked.connect(self.toggle_settings)
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.status_indicator)
        header_layout.addWidget(self.settings_button)
        layout.addWidget(header)
        
        # Settings panel (hidden by default)
        self.settings_panel = QFrame()
        self.settings_panel.setStyleSheet("""
            QFrame {
                background-color: #F5F5F5;
                border-bottom: 1px solid #DDD;
            }
        """)
        settings_layout = QVBoxLayout(self.settings_panel)
        settings_layout.setContentsMargins(12, 8, 12, 8)
        settings_layout.setSpacing(6)
        
        provider_row = QHBoxLayout()
        provider_label = QLabel("Provider:")
        provider_label.setFont(QFont("Arial", 10, QFont.Bold))
        provider_label.setFixedWidth(65)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["gemini", "openai", "modelscope"])
        self.provider_combo.setStyleSheet("""
            QComboBox {
                padding: 6px 10px;
                border: 1px solid #CCC;
                border-radius: 4px;
                background: white;
                font-size: 11px;
            }
        """)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_row.addWidget(provider_label)
        provider_row.addWidget(self.provider_combo, 1)
        settings_layout.addLayout(provider_row)
        
        api_key_row = QHBoxLayout()
        api_key_label = QLabel("API Key:")
        api_key_label.setFont(QFont("Arial", 10, QFont.Bold))
        api_key_label.setFixedWidth(65)
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Enter your API key")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setStyleSheet("""
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #CCC;
                border-radius: 4px;
                background: white;
                font-size: 11px;
            }
        """)
        self.save_api_button = QPushButton("Save")
        self.save_api_button.setFixedSize(50, 28)
        self.save_api_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #388E3C; }
        """)
        self.save_api_button.clicked.connect(self.save_api_key)
        
        api_key_row.addWidget(api_key_label)
        api_key_row.addWidget(self.api_key_input, 1)
        api_key_row.addWidget(self.save_api_button)
        settings_layout.addLayout(api_key_row)
        
        self.settings_panel.setVisible(False)
        layout.addWidget(self.settings_panel)
        
        # Conversation area
        self.conversation_scroll = QScrollArea()
        self.conversation_scroll.setWidgetResizable(True)
        self.conversation_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.conversation_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #FFFFFF;
            }
            QScrollBar:vertical {
                background: #F5F5F5;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #BBB;
                border-radius: 4px;
            }
        """)
        
        self.conversation_widget = QWidget()
        self.conversation_layout = QVBoxLayout(self.conversation_widget)
        self.conversation_layout.setAlignment(Qt.AlignTop)
        self.conversation_layout.setSpacing(4)
        self.conversation_layout.setContentsMargins(12, 12, 12, 12)
        
        self.conversation_scroll.setWidget(self.conversation_widget)
        layout.addWidget(self.conversation_scroll, 1)
        
        # Drop zone
        self.drop_zone = DropZone()
        self.drop_zone.folder_dropped.connect(self.on_folder_dropped)
        self.drop_zone.files_dropped.connect(self.on_files_dropped)
        layout.addWidget(self.drop_zone)
        
        # Input area
        input_frame = QFrame()
        input_frame.setStyleSheet("background-color: #FAFAFA; border-top: 1px solid #EEE;")
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 8, 12, 8)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask Copilot... (e.g., 'Show only the tumor and vessels')")
        self.input_field.setStyleSheet("""
            QLineEdit {
                padding: 10px 16px;
                border: 1px solid #DDD;
                border-radius: 20px;
                background: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #2196F3;
            }
        """)
        self.input_field.returnPressed.connect(self.on_send)
        
        self.send_button = QPushButton("Send")
        self.send_button.setFixedSize(80, 40)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border-radius: 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #1565C0; }
            QPushButton:disabled { background-color: #BBB; }
        """)
        self.send_button.clicked.connect(self.on_send)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        layout.addWidget(input_frame)
    
    @staticmethod
    def _resolve_prompt_path(filename: str) -> Optional[str]:
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "Resources", "prompts", filename),
            os.path.join(os.path.dirname(__file__), "prompts", filename),
            os.path.join(os.path.dirname(__file__), "..", "..", "prompts", filename),
            os.path.join(os.path.dirname(__file__), "..", "prompts", filename),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def load_system_prompt(self):
        prompt_path = self._resolve_prompt_path("system_prompt.txt")
        if prompt_path and os.path.exists(prompt_path):
            try:
                with open(prompt_path, 'r') as f:
                    self.system_prompt = f.read()
            except Exception:
                self.system_prompt = self.get_default_system_prompt()
        else:
            self.system_prompt = self.get_default_system_prompt()
    
    def _resolve_knowledge_path(self, filename: str) -> Optional[str]:
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "Resources", "knowledge", filename),
            os.path.join(os.path.dirname(__file__), "knowledge", filename),
            os.path.join(os.path.dirname(__file__), "..", "..", "knowledge", filename),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    def _load_examples(self) -> List[Dict]:
        """Load few-shot examples from slicer_examples.json."""
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
    
    def get_default_system_prompt(self) -> str:
        return """You are Slicer AI Copilot.

You control a 3D Slicer scene through a restricted action API.

Never output executable Python.
Never invent objects that are not present in the provided scene.
Never make a diagnosis or treatment recommendation.
Only use actions from the allowed action list.
If a requested object does not exist, report that clearly.
If a request is ambiguous, ask for clarification.
Return valid JSON only.

The current Slicer scene is provided separately.

The system validates every action before execution."""
    
    def add_welcome_message(self):
        msg = ChatMessage(
            role="assistant",
            content="Hello! I'm Slicer AI Copilot. Drop a case folder or ask me to control the scene.\n\nExamples:\n• \"Show the tumor\"\n• \"Hide the skin\"\n• \"Make the liver transparent\"\n• \"Zoom to the tumor\"\n• \"What structures are loaded?\"",
            timestamp=datetime.now()
        )
        self.add_message(msg)
    
    def toggle_settings(self):
        visible = self.settings_panel.isVisible()
        self.settings_panel.setVisible(not visible)
        if not visible:
            saved_key = os.getenv("LLM_API_KEY", "")
            if saved_key:
                self.api_key_input.setText(saved_key)
            saved_provider = os.getenv("LLM_PROVIDER", "gemini")
            idx = self.provider_combo.findText(saved_provider)
            if idx >= 0:
                self.provider_combo.setCurrentIndex(idx)
    
    def _on_provider_changed(self, provider):
        config = PROVIDER_CONFIGS.get(provider, {})
        base_url = config.get("base_url", "")
        model = config.get("model", "")
        self.llm_client.provider = provider
        self.llm_client.base_url = base_url
        self.llm_client.model = model
        self.llm_client._init_clients()
    
    def save_api_key(self):
        api_key = str(self.api_key_input.text).strip()
        if not api_key:
            self.add_message(ChatMessage(
                role="system",
                content="API key cannot be empty.",
                timestamp=datetime.now()
            ))
            return
        
        provider = str(self.provider_combo.currentText)
        
        try:
            os.environ["LLM_API_KEY"] = api_key
            os.environ["LLM_PROVIDER"] = provider
            self.llm_client.api_key = api_key
            self.llm_client.provider = provider
            config = PROVIDER_CONFIGS.get(provider, {})
            self.llm_client.base_url = config.get("base_url", "")
            self.llm_client.model = config.get("model", "")
            self.llm_client._init_clients()
            
            settings_dir = os.path.expanduser("~/.slicer_ai_copilot")
            os.makedirs(settings_dir, exist_ok=True)
            settings_file = os.path.join(settings_dir, "settings.json")
            with open(settings_file, 'w') as f:
                json.dump({"llm_api_key": api_key, "llm_provider": provider}, f)
            
            self.add_message(ChatMessage(
                role="system",
                content=f"API key saved. Testing connection to {provider}...",
                timestamp=datetime.now()
            ))
            self.settings_panel.setVisible(False)
            QTimer.singleShot(100, self._test_api_connection)
        except Exception as e:
            self.add_message(ChatMessage(
                role="system",
                content=f"Failed to save API key: {str(e)}",
                timestamp=datetime.now()
            ))
    
    def _test_api_connection(self):
        try:
            response = self.llm_client.complete(
                [{"role": "user", "content": "Reply with only the word OK"}],
                temperature=0.1,
                max_tokens=5
            )
            if response.content:
                self.add_message(ChatMessage(
                    role="system",
                    content=f"API connected! Provider: {self.llm_client.provider}, Model: {self.llm_client.model}",
                    timestamp=datetime.now()
                ))
            else:
                self.add_message(ChatMessage(
                    role="system",
                    content=f"API key saved but got empty response. Try sending a message to test.",
                    timestamp=datetime.now()
                ))
            self.set_state(UIState.IDLE)
        except Exception as e:
            self.add_message(ChatMessage(
                role="system",
                content=f"API test error: {str(e)}\nAPI key was saved. Try sending a message.",
                timestamp=datetime.now()
            ))
            self.set_state(UIState.IDLE)
    
    def load_saved_settings(self):
        settings_file = os.path.expanduser("~/.slicer_ai_copilot/settings.json")
        try:
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                api_key = settings.get("llm_api_key", "")
                provider = settings.get("llm_provider", "gemini")
                if api_key:
                    os.environ["LLM_API_KEY"] = api_key
                    os.environ["LLM_PROVIDER"] = provider
                    self.llm_client.api_key = api_key
                    self.llm_client.provider = provider
                    config = PROVIDER_CONFIGS.get(provider, {})
                    self.llm_client.base_url = config.get("base_url", "")
                    self.llm_client.model = config.get("model", "")
                    self.llm_client._init_clients()
                    if hasattr(self, 'api_key_input'):
                        self.api_key_input.setText(api_key)
                    if hasattr(self, 'provider_combo'):
                        idx = self.provider_combo.findText(provider)
                        if idx >= 0:
                            self.provider_combo.setCurrentIndex(idx)
        except Exception:
            pass
    
    def add_message(self, message: ChatMessage):
        self.conversation.append(message)
        widget = MessageWidget(message)
        self.conversation_layout.addWidget(widget)
        
        # Auto-scroll to bottom
        QTimer.singleShot(50, lambda: self.conversation_scroll.verticalScrollBar().setValue(
            self.conversation_scroll.verticalScrollBar().maximum
        ))
    
    def set_state(self, state: UIState):
        self.current_state = state
        self.status_indicator.set_state(state)
        
        self.input_field.setEnabled(state == UIState.IDLE)
        self.send_button.setEnabled(state == UIState.IDLE)
        
        if state == UIState.THINKING:
            self.input_field.setPlaceholderText("Thinking...")
        elif state == UIState.PROPOSING:
            self.input_field.setPlaceholderText("Proposing actions...")
        elif state == UIState.EXECUTING:
            self.input_field.setPlaceholderText("Executing...")
        elif state == UIState.VERIFYING:
            self.input_field.setPlaceholderText("Verifying...")
        else:
            self.input_field.setPlaceholderText("Ask Copilot...")
    
    def on_send(self):
        text = str(self.input_field.text).strip()
        if not text:
            return
        
        self.input_field.clear()
        self.process_user_message(text)
    
    def on_folder_dropped(self, folder_path):
        if isinstance(folder_path, (list, tuple)):
            folder_paths = [str(p) for p in folder_path if p]
        elif folder_path and folder_path.startswith('['):
            try:
                folder_paths = json.loads(folder_path)
                folder_paths = [str(p) for p in folder_paths if p]
            except Exception:
                folder_paths = [str(folder_path)]
        else:
            folder_paths = [str(folder_path)] if folder_path else []
        
        if not folder_paths:
            self.add_message(ChatMessage(
                role="system",
                content="No valid folder path provided.",
                timestamp=datetime.now()
            ))
            return
        
        self.add_message(ChatMessage(
            role="system",
            content=f"Scanning {len(folder_paths)} folder(s)...",
            timestamp=datetime.now()
        ))
        self.set_state(UIState.THINKING)
        
        try:
            all_results = []
            for fp in folder_paths:
                scan_result = self.file_manager.scan_folder(fp)
                if "error" in scan_result:
                    self.add_message(ChatMessage(
                        role="system",
                        content=f"Error scanning {fp}: {scan_result['error']}",
                        timestamp=datetime.now()
                    ))
                else:
                    all_results.append(scan_result)
            
            if not all_results:
                self.set_state(UIState.ERROR)
                QTimer.singleShot(2000, lambda: self.set_state(UIState.IDLE))
                return
            
            combined = {
                "model_files": [],
                "nifti_files": [],
                "nrrd_files": [],
                "dicom_series_groups": [],
                "other_files": []
            }
            for result in all_results:
                for key in combined:
                    combined[key].extend(result.get(key, []))
            
            summary = self.file_manager.get_detected_files_summary(combined)
            self.add_message(ChatMessage(
                role="assistant",
                content=summary,
                timestamp=datetime.now()
            ))
            
            self.set_state(UIState.IDLE)
            QTimer.singleShot(100, lambda: self.auto_import_from_folder(combined))
            
        except Exception as e:
            self.add_message(ChatMessage(
                role="system",
                content=f"Scan failed: {str(e)}",
                timestamp=datetime.now()
            ))
            self.set_state(UIState.ERROR)
            QTimer.singleShot(2000, lambda: self.set_state(UIState.IDLE))
    
    def auto_import_from_folder(self, scan_result):
        self.set_state(UIState.EXECUTING)
        
        imported = []
        failed = []
        
        try:
            import slicer.util
        except ImportError:
            self.add_message(ChatMessage(
                role="system",
                content="Slicer not available for import",
                timestamp=datetime.now()
            ))
            self.set_state(UIState.ERROR)
            QTimer.singleShot(2000, lambda: self.set_state(UIState.IDLE))
            return
        
        try:
            model_files = scan_result.get("model_files", [])
            for fpath in model_files:
                try:
                    node = slicer.util.loadModel(fpath)
                    if node:
                        imported.append(f"Model: {node.GetName()}")
                    else:
                        failed.append(f"{os.path.basename(fpath)}: loadModel returned None")
                except Exception as e:
                    failed.append(f"{os.path.basename(fpath)}: {str(e)}")
            
            nifti_files = scan_result.get("nifti_files", [])
            for fpath in nifti_files:
                try:
                    node = slicer.util.loadVolume(fpath)
                    if node:
                        imported.append(f"NIfTI: {node.GetName()}")
                    else:
                        failed.append(f"{os.path.basename(fpath)}: loadVolume returned None")
                except Exception as e:
                    failed.append(f"{os.path.basename(fpath)}: {str(e)}")
            
            nrrd_files = scan_result.get("nrrd_files", [])
            for fpath in nrrd_files:
                try:
                    node = slicer.util.loadVolume(fpath)
                    if node:
                        imported.append(f"NRRD: {node.GetName()}")
                    else:
                        failed.append(f"{os.path.basename(fpath)}: loadVolume returned None")
                except Exception as e:
                    failed.append(f"{os.path.basename(fpath)}: {str(e)}")
            
            dicom_groups = scan_result.get("dicom_series_groups", [])
            for i, group in enumerate(dicom_groups):
                if not isinstance(group, list):
                    continue
                dir_path = os.path.dirname(group[0]) if group else None
                if dir_path:
                    loaded = self._load_dicom_folder(dir_path)
                    if loaded:
                        imported.append(f"DICOM series {i+1}: {loaded}")
                    else:
                        for fpath in group:
                            try:
                                node = slicer.util.loadNodeFromFile(fpath)
                                if node:
                                    imported.append(f"File: {node.GetName()}")
                            except Exception:
                                failed.append(f"{os.path.basename(fpath)}: could not load")
            
            other_files = scan_result.get("other_files", [])
            for fpath in other_files:
                ext = os.path.splitext(fpath)[1].lower()
                if ext in ('.vtk', '.stl', '.obj', '.ply', '.nii', '.nii.gz', '.nrrd', '.nhdr'):
                    continue
                try:
                    node = slicer.util.loadNodeFromFile(fpath)
                    if node:
                        imported.append(f"File: {node.GetName()}")
                except Exception:
                    pass
        except Exception as e:
            failed.append(f"Unexpected error: {str(e)}")
        finally:
            if imported:
                msg = "Imported:\n" + "\n".join(f"  + {item}" for item in imported)
            else:
                msg = "No files were auto-imported."
            if failed:
                msg += "\n\nFailed:\n" + "\n".join(f"  - {item}" for item in failed)
            
            if not imported:
                msg += "\n\nTo load these files manually:\n"
                msg += "  1. Go to File > Add Data (or press Ctrl+O)\n"
                msg += "  2. Navigate to your folder\n"
                msg += "  3. Press Ctrl+A to select all files\n"
                msg += "  4. Click OK"
            
            self.add_message(ChatMessage(
                role="assistant",
                content=msg,
                timestamp=datetime.now()
            ))
            self.set_state(UIState.IDLE)
    
    def _load_dicom_folder(self, dir_path):
        """Load DICOM files from a folder using multiple fallback methods."""
        try:
            import slicer
            dicom_plugin = slicer.modules.dicom
            if dicom_plugin and hasattr(dicom_plugin, 'logic'):
                logic = dicom_plugin.logic
                if hasattr(logic, 'examineForLoad'):
                    loadable_list = logic.examineForLoad([dir_path])
                    if loadable_list:
                        for loadable in loadable_list:
                            if hasattr(loadable, 'files') and loadable.files:
                                success = logic.loadLoadable(loadable)
                                if success:
                                    return f"{len(loadable.files)} files loaded"
        except Exception:
            pass
        
        try:
            import slicer.util
            count = 0
            for fname in sorted(os.listdir(dir_path)):
                fpath = os.path.join(dir_path, fname)
                if not os.path.isfile(fpath):
                    continue
                try:
                    node = slicer.util.loadNodeFromFile(fpath)
                    if node:
                        count += 1
                except Exception:
                    continue
            if count > 0:
                return f"{count} files loaded individually"
        except Exception:
            pass
        
        return None
    
    def _load_dicom_file(self, fpath):
        """Load a single DICOM file."""
        try:
            import slicer.util
            node = slicer.util.loadVolume(fpath)
            if node:
                return node.GetName()
        except Exception:
            pass
        
        try:
            import slicer.util
            node = slicer.util.loadNodeFromFile(fpath)
            if node:
                return node.GetName()
        except Exception:
            pass
        
        return None
    
    def on_files_dropped(self, file_paths):
        if isinstance(file_paths, str):
            file_paths = [file_paths]
        file_paths = [str(p) for p in file_paths if p]
        
        if not file_paths:
            return
        
        self.add_message(ChatMessage(
            role="system",
            content=f"Importing {len(file_paths)} file(s)...",
            timestamp=datetime.now()
        ))
        self.set_state(UIState.EXECUTING)
        
        imported = []
        failed = []
        
        try:
            import slicer.util
        except ImportError:
            self.add_message(ChatMessage(
                role="system",
                content="Slicer not available for import",
                timestamp=datetime.now()
            ))
            self.set_state(UIState.ERROR)
            QTimer.singleShot(2000, lambda: self.set_state(UIState.IDLE))
            return
        
        try:
            for fpath in file_paths:
                ext = os.path.splitext(fpath)[1].lower()
                try:
                    if ext in ('.vtk', '.stl', '.obj', '.ply'):
                        node = slicer.util.loadModel(fpath)
                        if node:
                            imported.append(f"Model: {node.GetName()}")
                        else:
                            failed.append(f"{os.path.basename(fpath)}: loadModel returned None")
                    elif ext in ('.nii', '.nii.gz') or fpath.lower().endswith('.nii.gz'):
                        node = slicer.util.loadVolume(fpath)
                        if node:
                            imported.append(f"Volume: {node.GetName()}")
                        else:
                            failed.append(f"{os.path.basename(fpath)}: loadVolume returned None")
                    elif ext in ('.nrrd', '.nhdr'):
                        node = slicer.util.loadVolume(fpath)
                        if node:
                            imported.append(f"Volume: {node.GetName()}")
                        else:
                            failed.append(f"{os.path.basename(fpath)}: loadVolume returned None")
                    elif ext in ('.dcm', '.dicom'):
                        loaded = self._load_dicom_file(fpath)
                        if loaded:
                            imported.append(f"DICOM: {loaded}")
                        else:
                            failed.append(f"{os.path.basename(fpath)}: DICOM load returned None")
                    else:
                        node = slicer.util.loadNodeFromFile(fpath)
                        if node:
                            imported.append(f"File: {node.GetName()}")
                        else:
                            failed.append(f"{os.path.basename(fpath)}: unsupported file type ({ext})")
                except Exception as e:
                    failed.append(f"{os.path.basename(fpath)}: {str(e)}")
        except Exception as e:
            failed.append(f"Unexpected error: {str(e)}")
        finally:
            if imported:
                msg = "Imported:\n" + "\n".join(f"  + {item}" for item in imported)
            else:
                msg = "No files were imported"
            if failed:
                msg += "\n\nFailed:\n" + "\n".join(f"  - {item}" for item in failed)
            
            self.add_message(ChatMessage(
                role="assistant",
                content=msg,
                timestamp=datetime.now()
            ))
            self.set_state(UIState.IDLE)
    
    def on_import_selected(self, scan_result: Dict, selections: Dict):
        self.add_message(ChatMessage(
            role="system",
            content="Importing selected files...",
            timestamp=datetime.now()
        ))
        self.set_state(UIState.EXECUTING)
        
        result = self.file_manager.import_case(scan_result, selections)
        
        if result["success"]:
            msg = "Imported:\n" + "\n".join(f"  ✓ {item}" for item in result["imported"])
        else:
            msg = "Import completed with errors:\n"
            msg += "\n".join(f"  ✓ {item}" for item in result.get("imported", []))
            msg += "\n".join(f"  ✗ {item}" for item in result.get("failed", []))
        
        self.add_message(ChatMessage(
            role="assistant",
            content=msg,
            timestamp=datetime.now()
        ))
        self.set_state(UIState.IDLE)
    
    def process_user_message(self, text: str):
        self.add_message(ChatMessage(
            role="user",
            content=text,
            timestamp=datetime.now()
        ))
        
        if not self.llm_client.is_available():
            self.add_message(ChatMessage(
                role="system",
                content="LLM client not available. Check your API key in Settings.",
                timestamp=datetime.now()
            ))
            self.set_state(UIState.ERROR)
            QTimer.singleShot(3000, lambda: self.set_state(UIState.IDLE))
            return
        
        scene_summary = self.scene_manager.get_scene_summary()
        scene_text = format_scene_summary({
            "volumes": [o.model_dump() for o in scene_summary.volumes],
            "models": [o.model_dump() for o in scene_summary.models],
            "segmentations": [o.model_dump() for o in scene_summary.segmentations],
            "markups": [o.model_dump() for o in scene_summary.markups],
            "transforms": [o.model_dump() for o in scene_summary.transforms],
        })
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": f"Current Slicer scene:\n{scene_text}"},
        ]
        
        examples = self._load_examples()
        messages.extend(examples)
        
        for msg in self.conversation[-6:]:
            if msg.role == "user":
                messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                if msg.action_plan:
                    import json as _json
                    plan_summary = _json.dumps({
                        "reply": msg.action_plan.reply,
                        "actions": [{"type": a.type, **(getattr(a, '__dict__', {}) if hasattr(a, '__dict__') else {})} for a in msg.action_plan.actions]
                    })
                    messages.append({"role": "assistant", "content": plan_summary})
                elif msg.content:
                    messages.append({"role": "assistant", "content": msg.content})
        
        messages.append({"role": "user", "content": text})
        
        self.set_state(UIState.THINKING)
        QTimer.singleShot(0, lambda: self.call_llm(messages))
    
    def call_llm(self, messages: List[Dict]):
        try:
            prompt_path = self._resolve_prompt_path("action_prompt.txt")
            action_prompt = None
            if prompt_path and os.path.exists(prompt_path):
                try:
                    with open(prompt_path, 'r') as f:
                        action_prompt = f.read()
                except Exception:
                    pass
            if not action_prompt:
                action_prompt = self.get_default_action_prompt()
            
            full_messages = messages + [{"role": "system", "content": action_prompt}]
            
            response = self.llm_client.complete(
                full_messages,
                temperature=0.1,
                max_tokens=2048
            )
            
            if not response.content:
                self.handle_llm_error("Empty response from LLM")
                return
            
            self.handle_llm_response(response.content)
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            self.handle_llm_error(str(e))
    
    def get_default_action_prompt(self) -> str:
        return """Return ONLY valid JSON matching this schema:

{
  "version": "1.0",
  "reply": "Brief natural language response to user",
  "actions": [
    {"type": "SHOW", "target": "object_name"},
    {"type": "HIDE", "target": "object_name"},
    {"type": "SHOW_ONLY", "targets": ["obj1", "obj2"]},
    {"type": "SET_OPACITY", "target": "object_name", "value": 0.3},
    {"type": "SET_COLOR", "target": "object_name", "color": [1.0, 0.0, 0.0]},
    {"type": "RESET_DISPLAY", "target": "object_name"},
    {"type": "RESET_VIEW"},
    {"type": "ZOOM_TO", "target": "object_name"},
    {"type": "THREE_D_VIEW"},
    {"type": "AXIAL_VIEW"},
    {"type": "SAGITTAL_VIEW"},
    {"type": "CORONAL_VIEW"},
    {"type": "LIST_OBJECTS"},
    {"type": "LIST_VISIBLE_OBJECTS"}
  ]
}

Allowed actions: SHOW, HIDE, SHOW_ONLY, SET_OPACITY, SET_COLOR, RESET_DISPLAY, RESET_VIEW, ZOOM_TO, THREE_D_VIEW, AXIAL_VIEW, SAGITTAL_VIEW, CORONAL_VIEW, LIST_OBJECTS, LIST_VISIBLE_OBJECTS.

Only use object names from the current scene. If unsure, use LIST_OBJECTS first."""
    
    def handle_llm_response(self, response_text: str):
        try:
            data = json.loads(response_text)
            plan = ActionPlan.model_validate(data)
            
            self.pending_plan = plan
            
            # Show proposed actions
            self.set_state(UIState.PROPOSING)
            
            msg = ChatMessage(
                role="assistant",
                content="",
                timestamp=datetime.now(),
                action_plan=plan
            )
            self.add_message(msg)
            
            # Validate
            self.set_state(UIState.EXECUTING)
            valid, errors = self.validator.validate_plan(plan)
            
            if not valid:
                self.handle_validation_error(errors)
                return
            
            # Execute
            results = self.action_engine.execute_plan(plan)
            
            # Verify
            self.set_state(UIState.VERIFYING)
            verification_results = self.verifier.verify_plan(plan.actions, results)
            
            # Update message with verification
            msg.verification_results = verification_results
            self.refresh_last_message()
            
            # Final state
            all_passed = all(vr.passed for vr in verification_results)
            self.set_state(UIState.SUCCESS if all_passed else UIState.ERROR)
            
            # Reset to idle after delay
            QTimer.singleShot(2000, lambda: self.set_state(UIState.IDLE))
            
        except json.JSONDecodeError as e:
            self.handle_llm_error(f"Invalid JSON from LLM: {e}")
        except Exception as e:
            logger.error(f"Response handling failed: {e}")
            self.handle_llm_error(str(e))
    
    def handle_validation_error(self, errors: List[str]):
        error_msg = "Validation failed:\n" + "\n".join(f"  ✗ {e}" for e in errors)
        self.add_message(ChatMessage(
            role="system",
            content=error_msg,
            timestamp=datetime.now()
        ))
        self.set_state(UIState.ERROR)
        QTimer.singleShot(2000, lambda: self.set_state(UIState.IDLE))
    
    def handle_llm_error(self, error: str):
        self.add_message(ChatMessage(
            role="system",
            content=f"AI error: {error}\nYou can still use manual Slicer controls.",
            timestamp=datetime.now()
        ))
        self.set_state(UIState.ERROR)
        QTimer.singleShot(2000, lambda: self.set_state(UIState.IDLE))
    
    def refresh_last_message(self):
        """Refresh the last message widget to show verification results."""
        if self.conversation_layout.count() > 0:
            # Remove last widget
            item = self.conversation_layout.takeAt(self.conversation_layout.count() - 1)
            if item and item.widget():
                item.widget().deleteLater()
            
            # Re-add with verification
            last_msg = self.conversation[-1]
            widget = MessageWidget(last_msg)
            self.conversation_layout.addWidget(widget)


def create_chat_widget(parent=None):
    """Factory function to create the chat widget."""
    return SlicerAICopilotWidget(parent)