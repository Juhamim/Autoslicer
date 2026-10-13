AGENTS.md — Slicer AI Copilot

1. Project Overview

Slicer AI Copilot is a general-purpose AI assistant embedded directly inside 3D Slicer.

The goal is to let users interact with Slicer through natural language instead of manually navigating modules, scene trees, display settings, file import workflows, and visualization controls.

The product is not liver-specific. Liver is only the first demonstration dataset.

Core concept:

User
  ↓
Slicer AI Copilot chat overlay
  ↓
Qwen
  ↓
Structured action plan
  ↓
Safety / validation layer
  ↓
Slicer action engine
  ↓
3D Slicer
  ↓
Verification
  ↓
User

The assistant should understand the current Slicer scene, interpret natural-language requests, propose safe Slicer operations, execute only validated operations, and verify the resulting scene state.

The project is primarily aligned with the hackathon challenge:

N35 — Verified natural-language automation of 3D Slicer

It may also support N34 — Automated 3D Slicer case preparation pipeline

The project should remain focused on natural-language control and verified workflow automation rather than becoming a general medical diagnosis system.

2. Important Reference Architecture

A published SlicerChat project demonstrated a chatbot implemented directly as a custom 3D Slicer extension. It extracted information from the current Slicer MRML scene and passed that context to an LLM. It also used a separate process for LLM inference to avoid blocking Slicer during computation.

Our implementation should adopt the useful architectural ideas but remain much simpler and more focused for a hackathon.

We should NOT copy the research system's large local-model/RAG infrastructure unless it becomes necessary.

Our target architecture:

┌───────────────────────────────────────────────────────────┐
│                       3D SLICER                            │
│                                                           │
│  ┌─────────────────────┐       ┌────────────────────────┐ │
│  │   AI COPILOT UI     │       │      SLICER SCENE      │ │
│  │                     │       │                        │ │
│  │ Conversation        │       │ CT / MRI               │ │
│  │ Input               │       │ Segmentations          │ │
│  │ Action status       │       │ Models                  │ │
│  │ Verification        │       │ Markups                 │ │
│  └──────────┬──────────┘       └───────────┬────────────┘ │
│             │                              │              │
└─────────────┼──────────────────────────────┼──────────────┘
              │                              │
              ▼                              ▼
       ┌──────────────┐              ┌──────────────┐
       │ Qwen Client  │              │ Scene Manager│
       └──────┬───────┘              └──────┬───────┘
              │                             │
              └──────────────┬──────────────┘
                             ▼
                    ┌─────────────────┐
                    │ Action Planner  │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │    Validator    │
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │  Action Engine  │
                    └────────┬────────┘
                             ▼
                         Slicer API
                             │
                             ▼
                         Verification

3. Product Vision

Main user experience

A user should be able to:

Open 3D Slicer.

Open the Slicer AI Copilot panel.

Drop a patient/case folder.

Let the assistant identify supported files.

Import/open the relevant data.

Ask natural-language commands.

See Slicer perform the requested action.

See a verification result.

Examples:

"Open the CT scan."

"Show the liver."

"Hide the skin."

"Show only the tumor."

"Show the tumor and surrounding vessels."

"Make the liver transparent."

"Zoom to the tumor."

"Show the axial view."

"What structures are currently loaded?"

"What structures are currently visible?"

"Prepare this case for review."

4. Non-Goals

Do NOT turn this project into:

A medical diagnosis system.

A treatment recommendation system.

An autonomous surgical system.

A replacement for a clinician.

A new DICOM viewer.

A new 3D renderer.

A new segmentation engine.

A complete replacement for 3D Slicer.

A huge general-purpose RAG research system.

An unrestricted Python-code execution agent.

3D Slicer should provide the medical imaging, visualization, and processing infrastructure.

Our software is the AI interaction and verified automation layer.

5. Repository Structure

Recommended repository:

SlicerAICopilot/
│
├── AGENTS.md
├── README.md
├── LICENSE
│
├── SlicerAICopilot/
│   ├── __init__.py
│   ├── SlicerAICopilot.py
│   ├── chat_ui.py
│   ├── qwen_client.py
│   ├── scene_manager.py
│   ├── file_manager.py
│   ├── action_engine.py
│   ├── validator.py
│   ├── verification.py
│   ├── schemas.py
│   └── utils.py
│
├── prompts/
│   ├── system_prompt.txt
│   └── action_prompt.txt
│
├── knowledge/
│   ├── slicer_actions.json
│   └── slicer_examples.json
│
├── tests/
│   ├── test_validator.py
│   ├── test_action_engine.py
│   ├── test_scene_manager.py
│   └── test_file_manager.py
│
└── docs/
    ├── architecture.md
    └── demo.md

Do not place the project source code inside the Slicer installation directory.

The project should be independently version-controlled and loaded by Slicer as a custom/scripted extension.

6. Technology Choices

Required

Python

3D Slicer Python API

Qt/CTK UI through Slicer

Qwen API

JSON

Slicer MRML scene APIs

Optional later

Background worker/process for non-blocking Qwen requests

RAG

Additional file-format handlers

Streaming responses

More advanced Slicer automation

Avoid unless required

C++

Custom VTK algorithms

Custom rendering

Large external frameworks

Unnecessary dependencies

The first implementation should use the tools already provided by Slicer.

7. Slicer Extension

The main module must appear directly inside 3D Slicer.

Expected experience:

3D Slicer
├── Existing Slicer modules
└── Slicer AI Copilot

The user should not need to open a browser to use the assistant.

The assistant should be accessible as a Slicer module/panel.

The UI should contain:

┌────────────────────────────────────┐
│ 🤖 Slicer AI Copilot              │
├────────────────────────────────────┤
│                                    │
│ AI: Hello. What would you like     │
│     to do?                         │
│                                    │
│ User: Hide the skin.               │
│                                    │
│ AI: I found "Skin".                │
│     Proposed action: HIDE Skin     │
│                                    │
│     ✓ Skin hidden                  │
│                                    │
├────────────────────────────────────┤
│ Type a command...                  │
├────────────────────────────────────┤
│                       [ Send ]      │
└────────────────────────────────────┘

The UI should not obstruct the 3D view unnecessarily.

8. Qwen Integration

Qwen is the natural-language reasoning/planning layer.

Qwen should NOT directly receive unrestricted permission to execute Python.

Qwen should produce a constrained structured action plan.

Example user:

Hide the skin and show only the tumor.

Expected model output:

{
  "reply": "I will hide the skin and show only the tumor.",
  "actions": [
    {
      "type": "HIDE",
      "target": "Skin"
    },
    {
      "type": "SHOW_ONLY",
      "targets": ["Tumor"]
    }
  ]
}

The exact schema may evolve, but it must remain machine-validated.

9. Qwen System Prompt Principles

The system prompt must communicate:

The assistant operates a 3D Slicer scene.

It can only use explicitly allowed actions.

It must never generate arbitrary Python for direct execution.

It must not invent scene objects.

It should use the provided current-scene information.

It should ask for clarification when the target is ambiguous.

It should not make clinical diagnoses or treatment decisions.

It should distinguish current scene facts from assumptions.

It should return structured JSON.

It should prefer the smallest valid set of actions.

Example:

You are Slicer AI Copilot.

You control a 3D Slicer scene through a restricted action API.

Never output executable Python.
Never invent objects that are not present in the provided scene.
Never make a diagnosis or treatment recommendation.
Only use actions from the allowed action list.
If a requested object does not exist, report that clearly.
If a request is ambiguous, ask for clarification.
Return valid JSON only.

The current Slicer scene is provided separately.

The system validates every action before execution.

10. Current Scene Awareness

The assistant must be able to inspect the current Slicer MRML scene.

The scene manager should collect useful non-sensitive metadata such as:

{
  "volumes": [
    {
      "name": "CT",
      "type": "ScalarVolume",
      "visible": true
    }
  ],
  "models": [
    {
      "name": "Liver",
      "type": "Model",
      "visible": true,
      "opacity": 0.3
    },
    {
      "name": "Tumor",
      "type": "Model",
      "visible": true,
      "opacity": 1.0
    }
  ],
  "segmentations": [],
  "markups": [],
  "transforms": []
}

Do not send patient image pixels to Qwen merely to answer basic scene-control questions.

For initial implementation, send only the minimum scene metadata required for the requested action.

11. Scene Manager Responsibilities

scene_manager.py should:

Inspect MRML nodes.

List volumes.

List models.

List segmentations.

List markups.

Read visibility.

Read opacity.

Read relevant display properties.

Resolve object names safely.

Provide a compact scene description.

Avoid modifying the scene directly where possible.

Example API:

get_scene_summary()
get_models()
get_volumes()
get_segmentations()
find_node_by_name(name)
find_nodes_by_type(node_type)
get_visibility(node)
get_opacity(node)

Object matching should tolerate natural-language variations.

Example:

"portal vein"
"Portal Vein"
"portalvein"
"portal vein model"

may resolve to the same actual Slicer node if the match is unambiguous.

Never silently select a random object when multiple objects are plausible matches.

12. Action Engine

action_engine.py is the only layer allowed to modify the Slicer scene.

Initial supported actions:

File actions

OPEN_FOLDER
IMPORT_DICOM
LOAD_VOLUME
LOAD_MODEL
LOAD_SEGMENTATION

Visibility actions

SHOW
HIDE
SHOW_ONLY

Display actions

SET_OPACITY
SET_COLOR
RESET_DISPLAY

Camera actions

RESET_VIEW
ZOOM_TO
THREE_D_VIEW
AXIAL_VIEW
SAGITTAL_VIEW
CORONAL_VIEW

Scene inspection

LIST_OBJECTS
LIST_VISIBLE_OBJECTS

Only implement actions that are actually needed.

13. Action Schema

Use a predictable JSON schema.

Example:

{
  "version": "1.0",
  "reply": "I found the tumor and will show it.",
  "actions": [
    {
      "type": "SHOW",
      "target": "Tumor"
    }
  ]
}

For opacity:

{
  "type": "SET_OPACITY",
  "target": "Liver",
  "value": 0.3
}

For multiple targets:

{
  "type": "SHOW_ONLY",
  "targets": [
    "Tumor",
    "Portal Vein",
    "Vena Cava"
  ]
}

14. Validator

The validator is a mandatory safety boundary.

Pipeline:

Qwen
 ↓
JSON parser
 ↓
Schema validation
 ↓
Action allowlist
 ↓
Target validation
 ↓
Parameter validation
 ↓
Execution

The validator must reject:

Unknown action types.

Missing required fields.

Invalid opacity values.

Unknown target objects.

Arbitrary Python code.

Shell commands.

File-system commands outside the allowed file workflow.

Requests that attempt to bypass the action API.

Example:

ALLOWED_ACTIONS = {
    "SHOW",
    "HIDE",
    "SHOW_ONLY",
    "SET_OPACITY",
    "SET_COLOR",
    "RESET_VIEW",
    "ZOOM_TO",
    "THREE_D_VIEW",
    "AXIAL_VIEW",
    "SAGITTAL_VIEW",
    "CORONAL_VIEW",
    "LIST_OBJECTS",
    "LIST_VISIBLE_OBJECTS",
    "OPEN_FOLDER",
    "IMPORT_DICOM",
    "LOAD_VOLUME",
    "LOAD_MODEL",
    "LOAD_SEGMENTATION"
}

15. Never Execute Model-Generated Python Directly

This is a strict rule.

Bad:

Qwen
 ↓
"Here is Python code..."
 ↓
exec(code)

Do NOT implement this.

Correct:

Qwen
 ↓
structured action
 ↓
validator
 ↓
known Python function
 ↓
Slicer API

For example:

{
  "type": "HIDE",
  "target": "Skin"
}

maps to our own trusted function:

hide_node("Skin")

The model chooses the action; our software owns the implementation.

16. Verification Layer

Every modifying action should have a verification step when practical.

Example:

User:

Hide the skin.

System:

Proposed:
HIDE → Skin

Execute.

Then verify:

Skin visibility = False

UI:

✓ Skin hidden

For multiple operations:

✓ Liver hidden
✓ Tumor visible
✓ Portal Vein visible
✓ Skin hidden

The verification layer should inspect the actual Slicer state instead of trusting Qwen's response.

17. Human Control

The assistant is an automation tool, not an autonomous clinical decision-maker.

For low-risk visualization operations, the MVP may execute automatically after validation.

For potentially consequential or destructive operations, require confirmation.

Examples that should eventually require explicit confirmation:

DELETE
CLEAR_SCENE
OVERWRITE
SAVE/EXPORT
MODIFY PATIENT DATA
CLINICAL TRANSFORMATION WITH POTENTIAL DATA LOSS

Provide a visible stop/cancel mechanism for long-running operations.

18. Folder Drop Workflow

Users should be able to drag a patient/case folder into the Copilot.

Example:

Patient_001/
├── CT/
│   ├── image001.dcm
│   ├── image002.dcm
│   └── ...
├── segmentations/
│   ├── tumor.nii.gz
│   └── liver.nii.gz
└── models/
    ├── liver.vtk
    └── vessels.vtk

The file manager should:

Receive the folder path.

Recursively scan files.

Identify supported formats.

Group DICOM files into candidate series.

Identify NIfTI files.

Identify VTK/STL/OBJ/etc. where supported.

Present detected content.

Ask for clarification when necessary.

Import/open through Slicer APIs.

Verify imported nodes.

Example UI:

Detected case data

✓ CT DICOM series
✓ liver.nii.gz
✓ tumor.nii.gz
✓ liver.vtk
✓ vessels.vtk

[ Import Case ]

Do not blindly import every file.

19. Generic File Support

The product must remain general-purpose.

Potential supported formats:

DICOM
NIfTI
NRRD
VTK
STL
OBJ

Actual support should depend on what Slicer can reliably load.

Do not implement custom readers unless Slicer cannot handle the required format.

20. Generic Anatomy Support

Do not hard-code liver logic into the core architecture.

The assistant should work with:

Liver
Tumor
Lung
Brain
Kidney
Heart
Bone
Vessels
Segmentation
etc.

The liver case is simply the first test case.

Bad:

if "liver" in target:
    ...

Prefer:

resolve_scene_target(target)

The same command engine should work with any scene object.

21. Natural-Language Examples

Visibility

"Show the tumor."

"Hide the skin."

"Hide the bones."

"Show only the tumor."

"Show the tumor and vessels."

"Hide everything except the tumor."

Display

"Make the liver transparent."

"Set the tumor opacity to 80%."

"Make the tumor red."

Navigation

"Zoom to the tumor."

"Center on the liver."

"Show the axial view."

"Switch to 3D."

Scene questions

"What is loaded?"

"What structures are visible?"

"Is the tumor loaded?"

"Which segmentations are available?"

Case preparation

"Prepare this case for review."

"Load the CT and show the tumor."

"Give me a clean 3D view of the tumor and surrounding structures."

22. Ambiguity Handling

If the scene contains:

Tumor 1
Tumor 2
Tumor 3

and the user says:

"Hide the tumor."

Do not arbitrarily select one.

Ask:

I found three tumor objects:
- Tumor 1
- Tumor 2
- Tumor 3

Which one should I hide?

If there is only one tumor:

"Hide the tumor."

may resolve automatically.

23. Scene Context Must Be Fresh

Before executing an action, refresh the relevant scene information.

Do not rely indefinitely on an old scene snapshot.

Example:

User: Hide the skin.
Assistant: ✓ Done.

User: Show the skin.

The system should inspect the current state rather than assuming it.

24. Conversation Memory

Conversation history should be lightweight.

Example:

User:
Show only the tumor.

AI:
Done.

User:
Now make it red.

The assistant should understand that "it" refers to the currently relevant tumor.

However, conversation history must not override actual Slicer scene state.

The current scene is authoritative for what actually exists.

25. Medical Safety

This project is a software-assistance prototype.

The assistant must not:

Diagnose disease.

Recommend treatment.

Claim clinical certainty.

Claim that a visualization is clinically correct.

Claim that a segmentation is medically accurate unless independently verified.

Present predictions as measurements.

Pretend that a model is a clinician.

Use language such as:

"Based on the objects currently loaded in Slicer..."

"I found one object named Tumor."

"I changed the visualization."

"I cannot determine clinical significance from the scene alone."

For medical decisions, the user must remain in control.

26. Privacy

Initial architecture should minimize data sent to Qwen.

For basic commands:

"Hide the skin."

Qwen only needs:

Current objects:
Skin
Liver
Tumor

It does not need CT pixel data.

Do not send patient images or unnecessary patient-identifying information to an external model.

API keys must not be committed to Git.

Use environment variables or runtime configuration.

Never hard-code:

API_KEY = "..."

27. Qwen API Configuration

The Qwen client should support configuration through environment variables or UI configuration.

Example environment variables:

QWEN_API_KEY
QWEN_BASE_URL
QWEN_MODEL

The exact model and endpoint should be configurable rather than hard-coded.

The implementation should use Qwen's supported API interface available to the user's account/plan.

If the user's Qwen credits are tied to a restricted plan that does not permit custom application API calls, do not work around the restriction. Use an allowed API credential/plan.

28. Error Handling

Every external operation must fail gracefully.

Examples:

Qwen unavailable

AI service unavailable.

You can still use manual Slicer controls.

Invalid model output

The AI returned an invalid action plan.
No Slicer changes were made.

Unknown target

I couldn't find an object named "Tumor" in the current scene.

File import failure

The folder was detected, but no supported imaging series could be imported.

Ambiguous target

I found multiple matching structures.
Please choose one.

Never silently perform a different action.

29. UI States

The Copilot should visibly distinguish:

IDLE
THINKING
PROPOSING
EXECUTING
VERIFYING
SUCCESS
ERROR

Example:

● Thinking...

Then:

Proposed:
HIDE → Skin

Then:

Executing...

Then:

✓ Verified: Skin is hidden

30. MVP Scope

The minimum successful prototype must include:

Must have

Embedded Slicer Copilot UI.

Qwen connection.

Current scene inspection.

Natural-language commands.

Structured action output.

Action validation.

SHOW.

HIDE.

SHOW_ONLY.

SET_OPACITY.

ZOOM_TO.

Basic view switching.

Verification.

Folder drop.

Basic supported-file detection.

Basic DICOM import/opening.

Generic object handling.

Error handling.

Nice to have

Streaming Qwen responses.

Conversation memory.

RAG.

More file formats.

More Slicer actions.

Better object-name matching.

Rich verification UI.

Background Qwen worker.

31. Recommended Development Order

Do not build everything simultaneously.

Milestone 1 — Slicer extension

Open Slicer
 ↓
Load Copilot
 ↓
Chat panel appears

Milestone 2 — Qwen

User message
 ↓
Qwen
 ↓
Text response

Milestone 3 — Scene inspection

Slicer scene
 ↓
scene_manager
 ↓
JSON summary

Milestone 4 — First action

Implement:

SHOW
HIDE

Test:

"Hide the skin."

Milestone 5 — Multiple actions

Implement:

SHOW_ONLY
SET_OPACITY

Test:

"Show only the tumor and vessels."

Milestone 6 — Camera

Implement:

ZOOM_TO
AXIAL
SAGITTAL
CORONAL
3D

Milestone 7 — Verification

Every action:

Plan
 ↓
Validate
 ↓
Execute
 ↓
Verify

Milestone 8 — Folder drop

Drop folder
 ↓
Detect files
 ↓
Import
 ↓
Verify

Milestone 9 — Polish

Improve:

UI

errors

status indicators

confirmation

demo flow

Milestone 10 — Optional RAG

Only after the core system is stable.

32. Testing Strategy

Test the action engine independently from Qwen.

Example:

test_hide_skin()
test_show_tumor()
test_show_only_tumor()
test_set_opacity()
test_zoom_to_tumor()

Also test invalid requests:

test_unknown_action_rejected()
test_invalid_opacity_rejected()
test_unknown_target_rejected()
test_arbitrary_python_rejected()

The core system should remain safe even if Qwen produces bad output.

33. Demo Dataset

Use the existing liver dataset as the first demonstration because it provides:

CT
Liver
Tumor
Portal Vein
Vena Cava
Skin
Bone
Gallbladder

But do not encode these names as the only supported anatomy.

The demo should prove that the architecture is generic.

34. Hackathon Demo Script

Target demonstration:

Step 1

Drop a case folder.

Case detected:
✓ CT
✓ Liver
✓ Tumor
✓ Portal Vein
✓ Vena Cava
✓ Skin

Step 2

User:

Prepare this case.

Assistant imports/organizes the available data.

Step 3

User:

Show only the tumor and surrounding vessels.

System:

Proposed:
SHOW Tumor
SHOW Portal Vein
SHOW Vena Cava
HIDE other 3D structures

Then execute and verify.

Step 4

User:

Make the liver transparent.

System:

✓ Liver opacity = 30%

Step 5

User:

Zoom to the tumor.

System:

✓ Camera centered on Tumor

Step 6

User:

What structures are currently visible?

Assistant reads the real scene and answers.

This demonstrates:

IMPORT
  ↓
UNDERSTAND
  ↓
CONTROL
  ↓
VISUALIZE
  ↓
VERIFY

35. Definition of Done

The MVP is considered successful when a judge can:

Open 3D Slicer.

Open Slicer AI Copilot.

Drop a medical imaging folder.

See detected files.

Import the case.

Ask a natural-language command.

Watch Slicer change.

See a verification result.

Ask a follow-up command.

Observe that the assistant understands the current scene.

The most important demo statement is:

"The AI doesn't just tell you how to use Slicer. It understands the current Slicer scene and safely performs the requested operation."

36. Coding Rules for AI Coding Agents

When modifying this repository:

Always

Prefer small, focused changes.

Preserve the existing architecture.

Keep Slicer-specific code inside Slicer integration modules.

Keep Qwen API logic separate from scene logic.

Validate all model-generated actions.

Add tests for new action types.

Handle errors explicitly.

Use type hints where practical.

Keep functions small and understandable.

Comment only where behavior is non-obvious.

Never

Put API keys in source code.

Execute arbitrary LLM-generated Python.

Execute shell commands generated by the LLM.

Delete or overwrite patient data without explicit confirmation.

Invent Slicer API functions.

Assume an object exists without checking.

Hard-code the project around the liver.

Modify the Slicer installation.

Add heavy dependencies without a clear reason.

Replace Slicer functionality that already exists.

37. Architecture Boundaries

Maintain these boundaries:

chat_ui.py
    ↓
qwen_client.py
    ↓
schemas.py
    ↓
validator.py
    ↓
action_engine.py
    ↓
scene_manager.py
    ↓
3D Slicer API

File handling:

chat_ui.py
    ↓
file_manager.py
    ↓
Slicer import APIs
    ↓
scene_manager.py

Do not allow:

Qwen client → direct Slicer modification

Instead:

Qwen client
    ↓
structured response
    ↓
validator
    ↓
action engine

38. Future Architecture

If Qwen inference starts blocking Slicer:

Slicer
  │
  ├── UI process
  │
  └── AI worker process
          │
          └── Qwen

Communication can later use:

localhost HTTP

WebSocket

another suitable IPC mechanism

Do not introduce a complex process architecture until the simple implementation demonstrates the need.

39. Future RAG

RAG is optional.

Potential knowledge sources:

3D Slicer documentation
Slicer Python examples
Allowed action definitions
Project-specific workflows

RAG should improve:

Slicer API understanding.

Natural-language interpretation.

Correct action selection.

Explanations.

RAG must NOT bypass the validator.

Even if RAG tells the model how to perform something, execution still goes through the action API.

40. Core Principle

The central engineering principle is:

LLM = Understand and plan
        ↓
Validator = Decide what is allowed
        ↓
Action Engine = Execute trusted operations
        ↓
Slicer = Perform the actual work
        ↓
Verification = Confirm what actually happened

Never invert this relationship.

The AI should be powerful enough to understand the user, but constrained enough that it cannot arbitrarily control the medical-imaging environment.

41. Product Identity

Working name:

Slicer AI Copilot

Possible tagline:

"Talk to your medical data. Control your Slicer workspace."

Alternative:

"Natural-language control for 3D Slicer."

The project should be presented as a general Slicer automation assistant, with the liver case used as the first proof-of-concept.

42. Primary Hackathon Story

Problem:

3D Slicer provides powerful medical imaging capabilities, but users must navigate complex interfaces and understand many separate tools to perform routine visualization and case-preparation tasks.

Solution:

Slicer AI Copilot embeds a natural-language AI assistant directly into Slicer. It understands the current scene, translates user instructions into a restricted action plan, validates the plan, executes it through Slicer's APIs, and verifies the result.

Safety:

The LLM never receives unrestricted execution privileges. Every operation passes through a controlled action layer and verification step.

Hero interaction:

DROP CASE
   ↓
"Prepare this case."
   ↓
"Show only the tumor and vessels."
   ↓
"Make the liver transparent."
   ↓
"Zoom to the tumor."
   ↓
"What is currently visible?"
   ↓
VERIFIED RESULT

43. Agent Priority

When an AI coding agent has to choose between features, prioritize in this order:

1. Correctness
2. Safety
3. Working Slicer integration
4. Verification
5. Simple UX
6. Generic scene support
7. File import
8. Qwen quality
9. RAG
10. Cosmetic improvements

A small reliable action set is better than a large unreliable action set.

44. Final Development Target

The finished prototype should feel like:

                 3D SLICER
┌────────────────────────────────────────────────┐
│                                                │
│  ┌──────────────────────┐                     │
│  │ 🤖 SLICER COPILOT    │                     │
│  │                      │                     │
│  │ "Hide everything     │                     │
│  │  except tumor and    │                     │
│  │  vessels."           │                     │
│  │                      │                     │
│  │ Plan:                │                     │
│  │ ✓ Show Tumor         │                     │
│  │ ✓ Show Portal Vein   │                     │
│  │ ✓ Show Vena Cava     │                     │
│  │ ✓ Hide Skin          │                     │
│  │ ✓ Hide Bone          │                     │
│  │                      │                     │
│  │ ✓ Verified           │        3D VIEW      │
│  │                      │                     │
│  │ [Ask Copilot...]     │        🔴 Tumor     │
│  └──────────────────────┘        🔵 Vessels   │
│                                                │
└────────────────────────────────────────────────┘

The product is successful when the user can interact with Slicer itself through natural language, while Slicer remains the source of truth and the clinician/user remains in control.