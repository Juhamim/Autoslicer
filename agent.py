"""SlicerFlow Copilot - Interactive Terminal AI Agent.

Natural Language AI Agent running directly in the Python terminal.
Adheres strictly to the core principle:
AI understands. Rules validate. 3D Slicer executes. Verification checks. Humans approve.
"""

import os
import sys
import argparse
import time
import json
from typing import Optional, Dict, Any, List

# Ensure package directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.operation_registry import (
    get_supported_operations,
    get_unsupported_operation_message,
    is_supported_operation,
    SUPPORTED_OPERATIONS,
)
from core.workflow import WorkflowPlan, WorkflowStep, OperationStatus
from core.orchestrator import PipelineOrchestrator
from copilot.parser import RuleBasedParser
from copilot.planner import WorkflowPlanner
from copilot.llm_client import ExternalLLMClient
from analyzer.case_analyzer import CaseAnalyzer
from analyzer.metadata import CaseMetadata
from automation.code_generator import SlicerCodeGenerator
from automation.console_bridge import ConsoleBridge
from automation.slicer_interface import SlicerInterface
from validation.command_validator import CommandValidator


# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ANSI color codes for terminal display
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    WHITE = "\033[37m"
    BG_DARK = "\033[40m"


def print_banner():
    banner = rf"""{Colors.CYAN}{Colors.BOLD}
================================================================================
     ____  __ _                 ________                ______            _ __     __ 
    / __/ / (_)_______ _____   / ____/ /___ _      __  / ____/___  ____  (_) /___  / /_
   _\ \  / / / __/ -_) __/ _ \ / /_  / / __ \ | /| / / / /   / __ \/ __ \/ / / __ \/ __/
  /___/ /_/_/\__/\__/_/  \___//_/   /_/\____/ |/ |/_/  \____/\____/ /_/ /_/_/\____/\__/ 
                                                                  /_/                     
      From Natural Language to Verified & Reproducible 3D Slicer Workflows
================================================================================{Colors.RESET}
{Colors.DIM}AI understands * Rules validate * 3D Slicer executes * Verification checks * Humans approve{Colors.RESET}
"""
    print(banner)


class TerminalAIAgent:
    """Interactive Python Terminal AI Agent for 3D Slicer automation."""

    def __init__(
        self,
        case_path: Optional[str] = None,
        output_dir: Optional[str] = None,
        use_llm: bool = False,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.output_dir = output_dir or os.path.join(BASE_DIR, "outputs")
        os.makedirs(self.output_dir, exist_ok=True)

        self.case_path = case_path or ""
        self.case_metadata: Optional[CaseMetadata] = None

        self.use_llm = use_llm
        self.llm_client = ExternalLLMClient(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name
        )

        self.current_plan: Optional[WorkflowPlan] = None
        self.orchestrator = PipelineOrchestrator()
        self.slicer_interface = SlicerInterface()

        if self.case_path and os.path.exists(self.case_path):
            self.inspect_current_case(silent=True)

    def log(self, text: str, color: str = Colors.WHITE, bold: bool = False):
        style = (Colors.BOLD if bold else "") + color
        print(f"{style}{text}{Colors.RESET}")

    def inspect_current_case(self, silent: bool = False) -> Optional[CaseMetadata]:
        """Inspect and display case technical metadata."""
        if not self.case_path or not os.path.exists(self.case_path):
            if not silent:
                self.log(f"[-] No case file loaded or file does not exist: {self.case_path}", Colors.RED)
            return None

        self.case_metadata = CaseAnalyzer.analyze_case(self.case_path)
        if not silent:
            self.log(f"\n[+] Case Technical Inspection:", Colors.CYAN, bold=True)
            self.log(f"    File:       {self.case_metadata.file_name}")
            self.log(f"    Format:     {self.case_metadata.file_format}")
            self.log(f"    Modality:   {self.case_metadata.modality}")
            if self.case_metadata.dimensions:
                dim = self.case_metadata.dimensions
                self.log(f"    Dimensions: {dim[0]} × {dim[1]} × {dim[2]}")
            if self.case_metadata.spacing:
                spc = self.case_metadata.spacing
                self.log(f"    Spacing:    {spc[0]:.2f} × {spc[1]:.2f} × {spc[2]:.2f} mm")
            if self.case_metadata.intensity_min is not None:
                self.log(f"    Intensity:  [{self.case_metadata.intensity_min:.1f}, {self.case_metadata.intensity_max:.1f}] HU")
            status_color = Colors.GREEN if self.case_metadata.status == "VALID" else Colors.RED
            self.log(f"    Status:     {self.case_metadata.status}", status_color, bold=True)

        return self.case_metadata

    def process_query(self, user_query: str) -> Optional[WorkflowPlan]:
        """Convert natural language query into a validated, structured workflow plan."""
        self.log(f"\n[*] Processing Request: \"{user_query}\"...", Colors.YELLOW)

        # 1. Copilot parsing
        meta_dict = self.case_metadata.to_dict() if self.case_metadata else None
        if self.use_llm and self.llm_client.is_configured():
            self.log("    Using External LLM Parser...", Colors.DIM)
            intent = self.llm_client.parse_workflow(user_query, case_metadata=meta_dict)
        else:
            self.log("    Using Deterministic Rule-Based Parser...", Colors.DIM)
            intent = RuleBasedParser.parse(user_query, context=meta_dict)

        # 2. Check if supported
        if not intent.is_supported:
            self.log("\n[!] UNSUPPORTED REQUEST REJECTED:", Colors.RED, bold=True)
            print(intent.unsupported_reason)
            return None

        # 3. Build plan
        planner = WorkflowPlanner()
        plan = planner.plan(
            intent=intent,
            case_id=os.path.splitext(os.path.basename(self.case_path))[0] if self.case_path else "CASE_001",
            case_file_path=self.case_path
        )
        self.current_plan = plan

        # 4. Display proposed plan
        self.log(f"\n[+] Proposed Workflow Plan (Intent: {intent.intent}, Target: {intent.parameters.get('target_anatomy', 'bone')}):", Colors.CYAN, bold=True)
        for i, step in enumerate(plan.steps):
            self.log(f"    {i+1}. {step.display_name:<28} ({step.operation})", Colors.WHITE)

        # 5. Pre-execution Command & Topology Validation
        is_valid, messages, step_statuses = CommandValidator.validate_plan(plan, file_path=self.case_path)
        self.log("\n[+] Pre-Execution Rule Validation:", Colors.CYAN, bold=True)
        if is_valid:
            self.log("    [PASS] All operations whitelisted in registry", Colors.GREEN)
            self.log("    [PASS] Dependency ordering verified", Colors.GREEN)
            self.log("    [PASS] Input case file verified and accessible", Colors.GREEN)
            self.log("    STATUS: READY FOR EXECUTION", Colors.GREEN, bold=True)
        else:
            self.log("    [BLOCKED] Validation failed:", Colors.RED, bold=True)
            for msg in messages:
                self.log(f"    • {msg}", Colors.RED)

        return plan

    def show_slicer_code(self):
        """Display the synthesized 3D Slicer Python script."""
        if not self.current_plan:
            self.log("[-] No workflow plan active. Request a workflow first.", Colors.RED)
            return

        code = SlicerCodeGenerator.generate_slicer_script(
            plan=self.current_plan,
            input_file_path=self.case_path,
            output_dir=self.output_dir
        )
        self.log("\n--- Synthesized 3D Slicer Python Script ---", Colors.MAGENTA, bold=True)
        print(code)
        self.log("-------------------------------------------\n", Colors.MAGENTA)

    def execute_plan(self) -> bool:
        """Execute the current workflow plan with live terminal progress."""
        if not self.current_plan:
            self.log("[-] No workflow plan available to execute.", Colors.RED)
            return False

        if not self.current_plan.is_validated:
            self.log("[-] Plan has not passed validation. Cannot execute.", Colors.RED)
            return False

        self.log(f"\n[>] Executing Workflow Plan ({len(self.current_plan.steps)} steps)...", Colors.CYAN, bold=True)

        def step_callback(step: WorkflowStep, idx: int, total: int):
            status_symbol = {
                OperationStatus.PENDING: f"{Colors.DIM}PENDING{Colors.RESET}",
                OperationStatus.RUNNING: f"{Colors.YELLOW}RUNNING{Colors.RESET}",
                OperationStatus.SUCCESS: f"{Colors.GREEN}SUCCESS{Colors.RESET}",
                OperationStatus.WARNING: f"{Colors.YELLOW}WARNING{Colors.RESET}",
                OperationStatus.FAILED: f"{Colors.RED}FAILED{Colors.RESET}",
                OperationStatus.BLOCKED: f"{Colors.RED}BLOCKED{Colors.RESET}",
            }.get(step.status, step.status.value)

            timing = f" ({step.execution_time_seconds:.2f}s)" if step.execution_time_seconds > 0 else ""
            print(f"  Step {idx+1}/{total}: {step.display_name:<26} [{status_symbol}]{timing}")
            if step.status == OperationStatus.FAILED and step.error_details:
                print(f"      {Colors.RED}Reason: {step.error_details}{Colors.RESET}")
                print(f"      {Colors.YELLOW}Action: {step.suggested_action}{Colors.RESET}")

        def console_callback(line: str):
            # Print Slicer / execution engine log
            print(f"    {Colors.DIM}{line}{Colors.RESET}")

        executed_plan = self.orchestrator.execute(
            plan=self.current_plan,
            file_path=self.case_path,
            output_dir=self.output_dir,
            step_callback=step_callback,
            console_callback=console_callback
        )

        final_color = Colors.GREEN if executed_plan.final_status == OperationStatus.SUCCESS else Colors.RED
        self.log(f"\n[+] Execution Completed: {executed_plan.final_status.value}", final_color, bold=True)

        ctx = getattr(executed_plan, "context", {})
        outputs = ctx.get("output_files", {})
        if outputs:
            self.log("\n[+] Generated Verified Deliverables:", Colors.GREEN, bold=True)
            for k, v in outputs.items():
                self.log(f"    • {k.replace('_', ' ').title():<26}: {v}")

        return executed_plan.final_status == OperationStatus.SUCCESS

    def show_report(self):
        """Display generated Case Processing Report."""
        report_path = os.path.join(self.output_dir, f"{self.current_plan.case_id if self.current_plan else 'CASE'}_processing_report.md")
        if os.path.exists(report_path):
            self.log(f"\n--- Case Processing Report ({report_path}) ---", Colors.CYAN, bold=True)
            with open(report_path, "r", encoding="utf-8") as f:
                print(f.read())
            self.log("---------------------------------------------------\n", Colors.CYAN)
        else:
            self.log("[-] No processing report found. Execute a workflow first.", Colors.RED)

    def show_manifest(self):
        """Display generated Provenance Manifest."""
        manifest_path = os.path.join(self.output_dir, f"{self.current_plan.case_id if self.current_plan else 'CASE'}_manifest.json")
        if os.path.exists(manifest_path):
            self.log(f"\n--- Reproducibility Manifest ({manifest_path}) ---", Colors.CYAN, bold=True)
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(json.dumps(data, indent=2))
            self.log("---------------------------------------------------\n", Colors.CYAN)
        else:
            self.log("[-] No manifest found. Execute a workflow first.", Colors.RED)

    def interactive_repl(self):
        """Run the interactive natural language terminal REPL loop."""
        print_banner()

        # Report environment status
        s_status = self.slicer_interface.get_status()
        if s_status["is_available"]:
            self.log(f"[✓] 3D Slicer Found: {s_status['slicer_executable'] or s_status['python_slicer_executable']}", Colors.GREEN)
        else:
            self.log("[i] 3D Slicer executable not detected. Operating via Embedded Medical Engine.", Colors.CYAN)

        if self.case_path:
            self.log(f"[✓] Default Case Loaded: {os.path.basename(self.case_path)}", Colors.GREEN)
            self.inspect_current_case(silent=False)

        self.log("\nType any natural language command, or type 'help' for special commands, 'exit' to quit.\n", Colors.YELLOW)

        while True:
            try:
                prompt_str = f"{Colors.CYAN}{Colors.BOLD}SlicerFlow > {Colors.RESET}"
                cmd = input(prompt_str).strip()
            except (KeyboardInterrupt, EOFError):
                self.log("\nExiting SlicerFlow Copilot. Goodbye!", Colors.CYAN)
                break

            if not cmd:
                continue

            cmd_lower = cmd.lower()

            if cmd_lower in ("exit", "quit", "q"):
                self.log("Exiting SlicerFlow Copilot. Goodbye!", Colors.CYAN)
                break

            elif cmd_lower == "help":
                self.log("\n--- Terminal AI Agent Commands ---", Colors.CYAN, bold=True)
                self.log("  <natural language query>   e.g. 'Prepare this CT scan and generate a 3D model'")
                self.log("  case <file_path>           Set active medical imaging case (.nrrd, .nii.gz, .dcm)")
                self.log("  inspect                    Inspect currently loaded case metadata")
                self.log("  code                       View synthesized 3D Slicer Python script")
                self.log("  run / exec                 Execute the current validated workflow plan")
                self.log("  report                     Print human-readable Case Processing Report")
                self.log("  manifest                   Print JSON Provenance & Reproducibility Manifest")
                self.log("  toggle-llm                 Toggle between Rule-Based and External LLM parser")
                self.log("  exit / quit                Exit terminal\n")
                continue

            elif cmd_lower.startswith("case "):
                new_path = cmd[5:].strip().strip('"').strip("'")
                if os.path.exists(new_path):
                    self.case_path = new_path
                    self.log(f"[✓] Active case set to: {self.case_path}", Colors.GREEN)
                    self.inspect_current_case(silent=False)
                else:
                    self.log(f"[-] File not found: {new_path}", Colors.RED)
                continue

            elif cmd_lower == "inspect":
                self.inspect_current_case(silent=False)
                continue

            elif cmd_lower == "code":
                self.show_slicer_code()
                continue

            elif cmd_lower in ("run", "exec"):
                if not self.current_plan:
                    self.log("[-] No workflow planned yet. Type a natural language request first.", Colors.RED)
                else:
                    self.execute_plan()
                continue

            elif cmd_lower == "report":
                self.show_report()
                continue

            elif cmd_lower == "manifest":
                self.show_manifest()
                continue

            elif cmd_lower == "toggle-llm":
                self.use_llm = not self.use_llm
                mode_str = "External LLM API" if self.use_llm else "Rule-Based Offline Parser"
                self.log(f"[+] Parser Mode switched to: {mode_str}", Colors.YELLOW, bold=True)
                continue

            # Natural Language Request
            plan = self.process_query(cmd)
            if plan and plan.is_validated:
                # Human-in-the-loop approval gate
                try:
                    confirm = input(f"\n{Colors.BOLD}Execute this verified workflow now? [Y/n]: {Colors.RESET}").strip().lower()
                    if confirm in ("", "y", "yes"):
                        self.execute_plan()
                    else:
                        self.log("Execution deferred. Type 'run' when ready or 'code' to inspect Slicer script.", Colors.YELLOW)
                except (KeyboardInterrupt, EOFError):
                    break


def main():
    parser = argparse.ArgumentParser(description="SlicerFlow Copilot Terminal AI Agent")
    parser.add_argument("--case", type=str, default="", help="Path to input medical imaging volume (.nrrd, .nii, .dcm)")
    parser.add_argument("--query", type=str, default="", help="Natural language request (e.g. 'Prepare CT and generate 3D model')")
    parser.add_argument("--exec", dest="auto_exec", action="store_true", help="Auto-execute workflow if validated")
    parser.add_argument("--llm", action="store_true", help="Use external LLM client instead of rule parser")
    parser.add_argument("--api-key", type=str, default="", help="External LLM API Key (OpenAI / Gemini)")
    parser.add_argument("--output-dir", type=str, default="", help="Directory for generated deliverables")

    args = parser.parse_args()

    agent = TerminalAIAgent(
        case_path=args.case,
        output_dir=args.output_dir or None,
        use_llm=args.llm,
        api_key=args.api_key
    )

    if args.query:
        # Non-interactive CLI command execution
        print_banner()
        if agent.case_path:
            agent.inspect_current_case(silent=False)
        plan = agent.process_query(args.query)
        if plan and plan.is_validated and args.auto_exec:
            agent.execute_plan()
    else:
        # Interactive REPL mode
        agent.interactive_repl()


if __name__ == "__main__":
    main()
