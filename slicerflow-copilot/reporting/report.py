"""Case Processing Report Generator for SlicerFlow Copilot."""

import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from core.workflow import WorkflowPlan, OperationStatus


class ReportGenerator:
    """Generates human-readable Markdown and plain-text case processing reports."""

    SAFETY_DISCLAIMER = (
        "SAFETY DISCLAIMER: SlicerFlow Copilot is a research and medical engineering "
        "workflow automation software. It does not provide autonomous clinical diagnosis, "
        "prognostic predictions, or surgical treatment planning. All generated segmentations "
        "and 3D models require review and approval by qualified medical professionals."
    )

    @classmethod
    def generate_markdown_report(
        cls,
        plan: WorkflowPlan,
        input_file: str,
        output_files: Dict[str, str],
        case_summary: Optional[str] = None
    ) -> str:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Map status to symbols
        status_icons = {
            OperationStatus.SUCCESS.value: "✓",
            OperationStatus.WARNING.value: "⚠",
            OperationStatus.FAILED.value: "✗",
            OperationStatus.BLOCKED.value: "⊘",
            OperationStatus.PENDING.value: "○",
            OperationStatus.RUNNING.value: "⏳",
        }

        steps_lines = []
        for step in plan.steps:
            icon = status_icons.get(step.status.value, "•")
            duration_str = f" ({step.execution_time_seconds:.2f}s)" if step.execution_time_seconds > 0 else ""
            line = f"- [{icon}] **{step.display_name}**: {step.status.value}{duration_str}"
            if step.message:
                line += f" — *{step.message}*"
            if step.error_details:
                line += f"\n  - **Reason**: `{step.error_details}`"
            if step.suggested_action:
                line += f"\n  - **Suggested Action**: {step.suggested_action}"
            steps_lines.append(line)

        outputs_lines = []
        for name, path in output_files.items():
            outputs_lines.append(f"- ✓ **{name.replace('_', ' ').title()}**: `{os.path.basename(path)}`")

        report = f"""# SLICERFLOW COPILOT
## CASE PROCESSING REPORT

**Case ID**: `{plan.case_id}`  
**Plan ID**: `{plan.plan_id}`  
**Generated At**: `{timestamp_str}`  
**Final Status**: **`{plan.final_status.value}`**

---

### INPUT CASE
- **File**: `{os.path.basename(input_file)}`
- **Location**: `{input_file}`
{f"- **Inspection Details**:\n  {case_summary}" if case_summary else ""}

---

### WORKFLOW EXECUTION AUDIT
{chr(10).join(steps_lines)}

---

### GENERATED OUTPUTS
{chr(10).join(outputs_lines) if outputs_lines else "_No export artifacts generated._"}

---

### MEDICAL POSITIONING & COMPLIANCE
> {cls.SAFETY_DISCLAIMER}
"""
        return report

    @classmethod
    def save_report(cls, report_text: str, output_path: str) -> str:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        return output_path
