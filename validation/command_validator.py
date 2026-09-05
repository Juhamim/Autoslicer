"""Command and Workflow Topology Validator.

Validates operations before execution:
1. Supported in registry whitelist.
2. Valid dependency order (e.g. load before segment, segment before 3d model).
3. Required input availability.
"""

from typing import Tuple, List, Dict
import os

from core.operation_registry import is_supported_operation, SUPPORTED_OPERATIONS
from core.workflow import WorkflowPlan, OperationStatus


class CommandValidator:
    """Pre-execution workflow topology and prerequisite validator."""

    @classmethod
    def validate_plan(cls, plan: WorkflowPlan, file_path: str = "") -> Tuple[bool, List[str], Dict[str, str]]:
        messages: List[str] = []
        step_statuses: Dict[str, str] = {}
        is_valid = True

        if not plan.steps:
            return False, ["Workflow contains no operations."], {}

        # 1. Check input file
        effective_file = file_path
        if not effective_file and plan.steps:
            effective_file = plan.steps[0].parameters.get("file_path", "")

        if not effective_file or not os.path.exists(effective_file):
            messages.append(f"Input case file is missing or does not exist: {effective_file}")
            is_valid = False

        executed_or_preceding: List[str] = []

        for step in plan.steps:
            op = step.operation

            # 2. Whitelist check
            if not is_supported_operation(op):
                step_statuses[op] = "BLOCKED"
                messages.append(f"Operation '{op}' is not supported by the current workflow registry.")
                is_valid = False
                continue

            op_meta = SUPPORTED_OPERATIONS[op]
            prereqs = op_meta.get("requires", [])

            # 3. Dependency topology check
            missing_prereqs = [p for p in prereqs if p not in executed_or_preceding]
            if missing_prereqs:
                step_statuses[op] = "BLOCKED"
                prereq_names = ", ".join(missing_prereqs)
                messages.append(f"Operation '{op}' requires prior completion of: {prereq_names}")
                is_valid = False
            else:
                step_statuses[op] = "PASS"

            executed_or_preceding.append(op)

        plan.is_validated = is_valid
        plan.validation_messages = messages
        return is_valid, messages, step_statuses
