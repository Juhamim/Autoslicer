"""Workflow data models for SlicerFlow Copilot."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional
import time
import uuid


class OperationStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


@dataclass
class WorkflowStep:
    operation: str
    display_name: str
    status: OperationStatus = OperationStatus.PENDING
    parameters: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error_details: Optional[str] = None
    suggested_action: Optional[str] = None
    outputs: Dict[str, Any] = field(default_factory=dict)
    execution_time_seconds: float = 0.0
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    def start(self):
        self.status = OperationStatus.RUNNING
        self.start_time = time.time()

    def complete(self, message: str = "Completed successfully", outputs: Optional[Dict[str, Any]] = None):
        self.status = OperationStatus.SUCCESS
        self.message = message
        self.end_time = time.time()
        if self.start_time:
            self.execution_time_seconds = round(self.end_time - self.start_time, 3)
        if outputs:
            self.outputs.update(outputs)

    def warn(self, message: str, suggested_action: Optional[str] = None, outputs: Optional[Dict[str, Any]] = None):
        self.status = OperationStatus.WARNING
        self.message = message
        self.suggested_action = suggested_action
        self.end_time = time.time()
        if self.start_time:
            self.execution_time_seconds = round(self.end_time - self.start_time, 3)
        if outputs:
            self.outputs.update(outputs)

    def fail(self, message: str, error_details: Optional[str] = None, suggested_action: Optional[str] = None):
        self.status = OperationStatus.FAILED
        self.message = message
        self.error_details = error_details
        self.suggested_action = suggested_action or "Verify case input data and check execution environment."
        self.end_time = time.time()
        if self.start_time:
            self.execution_time_seconds = round(self.end_time - self.start_time, 3)

    def block(self, message: str, suggested_action: Optional[str] = None):
        self.status = OperationStatus.BLOCKED
        self.message = message
        self.suggested_action = suggested_action or "Fulfill prior workflow prerequisites before retrying."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "display_name": self.display_name,
            "status": self.status.value,
            "parameters": self.parameters,
            "message": self.message,
            "error_details": self.error_details,
            "suggested_action": self.suggested_action,
            "execution_time_seconds": self.execution_time_seconds,
            "outputs": {k: str(v) if not isinstance(v, (int, float, bool, str, list, dict)) else v for k, v in self.outputs.items()}
        }


@dataclass
class WorkflowPlan:
    case_id: str
    steps: List[WorkflowStep] = field(default_factory=list)
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    is_validated: bool = False
    validation_messages: List[str] = field(default_factory=list)
    final_status: OperationStatus = OperationStatus.PENDING
    created_at: float = field(default_factory=time.time)

    def add_step(self, step: WorkflowStep):
        self.steps.append(step)

    def get_step(self, operation: str) -> Optional[WorkflowStep]:
        for s in self.steps:
            if s.operation == operation:
                return s
        return None

    def operations_list(self) -> List[str]:
        return [step.operation for step in self.steps]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "case_id": self.case_id,
            "is_validated": self.is_validated,
            "validation_messages": self.validation_messages,
            "final_status": self.final_status.value,
            "operations": self.operations_list(),
            "steps": [step.to_dict() for step in self.steps]
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorkflowPlan":
        steps = []
        for s_data in d.get("steps", []):
            st = OperationStatus(s_data.get("status", "PENDING"))
            step = WorkflowStep(
                operation=s_data.get("operation", ""),
                display_name=s_data.get("display_name", ""),
                status=st,
                parameters=s_data.get("parameters", {}),
                message=s_data.get("message", ""),
                error_details=s_data.get("error_details"),
                suggested_action=s_data.get("suggested_action"),
                outputs=s_data.get("outputs", {}),
                execution_time_seconds=s_data.get("execution_time_seconds", 0.0)
            )
            steps.append(step)

        return cls(
            case_id=d.get("case_id", ""),
            steps=steps,
            plan_id=d.get("plan_id", str(uuid.uuid4())[:8]),
            is_validated=d.get("is_validated", False),
            validation_messages=d.get("validation_messages", []),
            final_status=OperationStatus(d.get("final_status", "PENDING")),
        )
