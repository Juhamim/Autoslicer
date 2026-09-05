"""Workflow Planner for SlicerFlow Copilot.

Transforms structured parsed intents into an ordered, executable WorkflowPlan.
"""

from typing import Optional, Dict, Any

from core.workflow import WorkflowPlan, WorkflowStep, OperationStatus
from core.operation_registry import SUPPORTED_OPERATIONS
from .schemas import ParsedWorkflowIntent


class WorkflowPlanner:
    """Plans a sequence of WorkflowSteps from a ParsedWorkflowIntent."""

    @classmethod
    def plan(
        cls,
        intent: ParsedWorkflowIntent,
        case_id: str = "CASE_001",
        case_file_path: Optional[str] = None
    ) -> WorkflowPlan:
        plan = WorkflowPlan(case_id=case_id)

        if not intent.is_supported or not intent.operations:
            plan.final_status = OperationStatus.BLOCKED
            plan.validation_messages.append(
                intent.unsupported_reason or "Workflow blocked: No supported operations found."
            )
            return plan

        for op_name in intent.operations:
            op_meta = SUPPORTED_OPERATIONS.get(op_name, {})
            display_name = op_meta.get("display_name", op_name.replace("_", " ").title())

            # Compile parameters
            step_params: Dict[str, Any] = {}
            if case_file_path:
                step_params["file_path"] = case_file_path

            if op_name == "segment":
                step_params["target_anatomy"] = intent.parameters.get("target_anatomy", "bone")
                step_params["lower_threshold"] = intent.parameters.get("lower_threshold", 250.0)
                step_params["upper_threshold"] = intent.parameters.get("upper_threshold", 2000.0)

            elif op_name == "generate_model":
                step_params["export_format"] = intent.parameters.get("export_format", "stl")
                step_params["smooth_iterations"] = 15

            elif op_name == "preprocess":
                step_params["window_preset"] = "bone" if intent.parameters.get("target_anatomy") == "bone" else "default"

            step = WorkflowStep(
                operation=op_name,
                display_name=display_name,
                parameters=step_params,
                message=f"Prepared for {display_name}"
            )
            plan.add_step(step)

        return plan
