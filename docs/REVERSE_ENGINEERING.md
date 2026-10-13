# Reverse Engineering — Full Code Analysis

A line-by-line reconstruction of how Slicer AI Copilot actually works: what each module owns, how
data flows, where the state lives, and where the implementation diverges from its own specification.

**Scope.** All 9 Python modules (1,946 LOC), 3 prompt/knowledge artefacts, and 101 unit tests as of
this commit. Every claim below cites `file:line` so it can be checked.

---

## 1. System Inventory

| Module | LOC | Responsibility | Reads Slicer | Writes Slicer | Calls LLM |
| ------ | --- | -------------- | :----------: | :-----------: | :--------: |
| `SlicerAICopilot.py` | 302 | Module registration, dependency bootstrap, logic facade | ✅ | via logic | ✅ |
| `chat_ui.py` | 1462 | Qt panel, DnD, settings, status, orchestration | ✅ | via engine | ✅ |
| `action_engine.py` | 411 | The **only** scene-mutating layer | ✅ | ✅ | ❌ |
| `scene_manager.py` | 259 | MRML enumeration + display property get/set | ✅ | ✅ | ❌ |
| `verification.py` | 347 | Post-execution state assertions | ✅ | ❌ | ❌ |
| `validator.py` | 203 | Allowlist + parameter + target policy | ✅ read | target rewrite | ❌ |
| `file_manager.py` | 244 | Folder scan + DICOM/NIfTI/NRRD/mesh import | ✅ | via `slicer.util` | ❌ |
| `llm_client.py` | 302 | OpenAI-compatible transport | ❌ | ❌ | ✅ |
| `schemas.py` | 173 | Pydantic contract + allowlist | ❌ | ❌ | ❌ |
| `utils.py` | 162 | Fuzzy match, magic bytes, formatting | ❌ | ❌ | ❌ |

### Singletons

Every component is a module-level singleton with an accessor:

```text
SceneManager   ← get_scene_manager()      ActionEngine  ← get_action_engine()
Validator      ← get_validator()         Verifier     ← get_verifier()
LLMClient      ← get_llm_client()        FileManager  ← get_file_manager()
```

Consequences:

- **Pros** — the UI and the logic facade share one `SceneManager`, so there is no stale duplicated
  state. Tests can monkeypatch `module._instance` to inject fakes.
- **Cons** — no lifecycle management. Constructing a client during import triggers
  `_init_clients()` immediately (`llm_client.py:68`), so merely importing the library performs I/O
  configuration. A `reset_for_tests()` hook per module would make isolation cleaner.

---

## 2. Boot Sequence

```text
1. Slicer scans module paths, finds SlicerAICopilot/SlicerAICopilot.py
2. SlicerAICopilot.__init__(parent)
     ├─ sets title/categories/contributors/helpText          (lines 50–68)
     ├─ loads Resources/Icons/SlicerAICopilot.png → qt.QIcon  (lines 75–83)
     └─ registers slicer.modules.sliceraicopilot             (lines 86–87)
3. Module import triggers dependency bootstrap                (lines 25–42)
     ├─ import openai    → on ImportError: slicer.util.pip_install("openai>=1.0.0")
     └─ import pydantic  → on ImportError: slicer.util.pip_install("pydantic>=2.0.0")
4. User opens the module → SlicerAICopilotWidget.setup()      (line 99)
     ├─ self.logic = SlicerAICopilotLogic()                   (line 103)
     │     └─ resolves all six singletons                     (lines 152–164)
     └─ self.chat_widget = create_chat_widget(self.parent)   (line 106)
5. SlicerAICopilotWidget.__init__ → load_saved_settings()    (chat_ui.py:858)
```

### Notable boot details

**Runtime `pip_install` inside the import path** (lines 24–42) is convenient and also risky: it
performs a network install during module load. It is guarded by `try/except` and degrades to a
warning, but on a locked-down clinical workstation with no outbound network the user gets a silent
degradation rather than a clear error. A preflight check in `helpText` would be better.

**Graceful degradation is pervasive.** Every Slicer import is guarded:

```python
try:
    import slicer
    from slicer import vtkMRMLScalarVolumeNode, ...
    SLICER_AVAILABLE = True
except ImportError:
    SLICER_AVAILABLE = False
    slicer = None
```

This is what allows the 101 unit tests to run on bare CPython with no Slicer install — a deliberate
and well-executed architectural decision.

**Scene-close cleanup** (`SlicerAICopilot.py:125–139`) clears the pending plan, wipes the
conversation, rebuilds the welcome message, and resets to `IDLE`. This prevents a stale plan from
executing against a scene that has been replaced.

---

## 3. Data Flow — One Request End to End

The chat path, with exact line references:

```text
①  on_send()                                            chat_ui.py:912
        │  reads self.input.text, appends user ChatMessage to self.conversation
        ▼
②  process_user_message(text)                           chat_ui.py:1265
        ├─ add_message(user)                                       :1266
        ├─ if not llm_client.is_available() → error + return        :1272
        ├─ scene_manager.get_scene_summary()          ◀── LIVE MRML :1282
        ├─ format_scene_summary(...)                   ◀── to text :1283
        ├─ build messages: system + scene + examples + history + user :1291
        ├─ set_state(THINKING)                                    :1315
        └─ QTimer.singleShot(0, lambda: call_llm(messages))        :1316
        ▼
③  call_llm(messages)                                  chat_ui.py:1318
        ├─ load action_prompt.txt                                :1320
        ├─ messages + [{"system": action_prompt}]                :1331
        └─ llm_client.complete(..., temperature=0.1,
                               max_tokens=2048)   ◀── BLOCKS UI THREAD :1333
        ▼
④  handle_llm_response(text)                           chat_ui.py:1377
        ├─ json.loads(text)                                      :1379
        ├─ ActionPlan.model_validate(data)      ◀── GATE 2 SCHEMA :1380
        ├─ self.pending_plan = plan                              :1382
        ├─ add_message(assistant with plan)  → PROPOSING         :1385–1393
        ├─ validator.validate_plan(plan)      ◀── GATE 3 POLICY  :1397
        │     └─ on failure → handle_validation_error → ERROR
        ├─ action_engine.execute_plan(plan)    ◀── MUTATION      :1404
        │     └─ fail-fast break on first error
        ├─ verifier.verify_plan(actions, results) ◀── GATE 4 EVIDENCE :1408
        ├─ msg.verification_results = verification_results       :1411
        ├─ refresh_last_message()   → rebuilds the message widget :1412
        └─ set_state(SUCCESS if all passed else ERROR)           :1415–1416
        ▼
⑤  QTimer.singleShot(2000, set_state(IDLE))            chat_ui.py:1419
```

### The scene snapshot is genuinely fresh

Step ② calls `get_scene_summary()` on **every** request and never caches it
(`chat_ui.py:1282`). There is no memoisation anywhere in `SceneManager`. This satisfies
`AGENTS.md` §23 ("Scene Context Must Be Fresh") by construction rather than by discipline.

---

## 4. The MRML Abstraction — `scene_manager.py`

### Enumeration

Five parallel methods, each calling `GetNodesByClass()` and wrapping results in `SceneObject`:

| Method | MRML class | Reads |
| ------ | ---------- | ------ |
| `get_volumes()` | `vtkMRMLScalarVolumeNode` | visibility only |
| `get_models()` | `vtkMRMLModelNode` | visibility, opacity, colour |
| `get_segmentations()` | `vtkMRMLSegmentationNode` | visibility, opacity |
| `get_markups()` | `vtkMRMLMarkupsNode` | visibility only |
| `get_transforms()` | `vtkMRMLTransformNode` | nothing (always `visible=True`) |

> ⚠️ **Transform visibility is a fiction.** `get_transforms()` hardcodes `visible=True`
> (`scene_manager.py:145`). `vtkMRMLTransformNode` has no display node, so there is nothing to read.
> The field is misleading: the model is told transforms are visible when the concept does not apply
> to them.

### Display property access

All display mutation funnels through the node's display node:

```python
def set_visibility(self, node, visible):
    display_node = node.GetDisplayNode()
    if display_node:
        display_node.SetVisibility(visible)
        return True
    return False          # ← silent False when there is no display node
```

Returning `False` on a missing display node is indistinguishable from a genuine write failure at the
call site — both become `ActionResult(False, "Failed to ...")`. Node types without display nodes
(markups in some configurations, label maps) will therefore fail confusingly.

### Node lookup — exact then fuzzy

```python
def find_node_by_name(self, name):
    nodes = self.scene.GetNodesByName(name)
    return nodes.GetItemAsObject(0) if nodes.GetNumberOfItems() > 0 else None

def find_matching_targets(self, query):
    return find_matching_objects(query, self.get_all_object_names())
```

Exact MRML lookup first (fast, unambiguous), then normalised substring matching as a fallback.
Critically, `find_node_by_name` returns `None` rather than raising when the name is absent — which is
what makes the validator's "ground the target in reality" check implementable.

---

## 5. Fuzzy Matching — `utils.fuzzy_match()`

The natural-language affordance the whole product rests on. Only 20 lines, and it carries real
weight:

```python
def fuzzy_match(query, candidates):
    query_lower = query.lower().replace(" ", "").replace("_", "").replace("-", "")
    matches = []
    for candidate in candidates:
        candidate_lower = candidate.lower().replace(" ", "").replace("_", "").replace("-", "")
        if query_lower == candidate_lower:
            matches.insert(0, candidate)                                  # exact → front
        elif query_lower in candidate_lower or candidate_lower in query_lower:
            matches.append(candidate)                                     # substring
        elif query_lower.replace("the", "") in candidate_lower:
            matches.append(candidate)                                     # article-stripped
    return matches
```

Normalisation strips spaces, underscores and hyphens, lowercases — so `Portal_Vein`,
`portal vein`, and `PORTAL-VEIN` collapse to `portalvein`. The `insert(0, …)` gives exact matches
priority. Articled phrasings ("the tumor") are handled by the third branch.

Weaknesses are documented in [§6](#6-known-issues-and-limitations): bidirectional substring matching
without a length floor, and `str.replace("the", "")` applied to the whole query string rather than
only a leading article.

---

## 6. File Detection — `utils.get_file_type()`

Two-tier strategy: extension first, magic bytes as fallback.

```text
.dcm / .dicom ──────────────────────────▶ DICOM
.nii / .nii.gz ─────────────────────────▶ NIfTI
.nrrd / .nhdr ──────────────────────────▶ NRRD
.vtk / .stl / .obj / .ply ──────────────▶ MODEL
(no extension) ─────────────────────────▶ _detect_by_content()
```

Note `.nii.gz` needs `endswith` rather than `Path.suffix`, because `Path("x.nii.gz").suffix` is
`.gz` — the code gets this right (`utils.py:54`).

`_detect_by_content()` reads the first 256 bytes and checks:

| Signal | Detected as |
| ------ | ----------- |
| `header[128:132] == b'DICM'` | DICOM |
| `header[:3] == b'\x1f\x8b\x08'` | NIfTI |
| `header[:4] == b'<?xml'` / `b'<VTK'` | MODEL |
| `header[:4] == b'NRRD'` | NRRD |
| `# vtk` / `vtkdatafile` in first 128 bytes | MODEL |
| `itkversion` / `nrrd` in first 128 bytes | NRRD |

Every byte check except NRRD is **redundant** with the extension table, since only extension-less
files reach this function — which is exactly the case where magic bytes fail (a DICOM file with no
extension still has `DICM` at 128, so that one earns its keep). Two entries are outright broken; see
[§6](#6-known-issues-and-limitations).

### Folder scanning and DICOM grouping

```python
def scan_folder_for_files(folder_path):
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            ...  classify and bucket
```

Recursive walk, categorised into `dicom_series`, `nifti_files`, `nrrd_files`, `model_files`,
`other_files`. Symlink loops are unguarded (`os.walk` defaults to not following them, so this is
actually safe by default).

`group_dicom_series()` groups **by parent directory only** (`utils.py:140`) — it does not read
DICOM headers, so it cannot distinguish two series inside one folder. `AGENTS.md` §18 calls for
`SeriesInstanceUID` grouping. The simplification is honest but undocumented in the UI, so a folder
holding two series presents as one.

### The four-strategy DICOM fallback

`file_manager._load_dicom_folder()` (lines 180–233) tries, in order:

1. `dicom_plugin.logic.examineForLoad([dir])` → `loadLoadable(loadable)`
2. `dicom_plugin.logic.loadDirectory(dir)`
3. `dicom_plugin.crawler.crawl([dir])`
4. `slicer.util.loadNodeFromFile(f)` over `os.listdir`

Every attempt is individually wrapped in `try/except: pass`. **This is a deliberate resilience
strategy**, not sloppiness — it maximises the chance of importing something from a folder that
differs from the expected layout. The cost is that a genuine failure produces no diagnostic: the
method returns `None` and the caller reports a generic `"load failed"`.

---

## 7. State Machine — The UI

`UIState` (`chat_ui.py:80`) is a 7-state enum with colour and label maps:

```text
     ┌──────────────────────────────────────────────────┐
     ▼                                                  │
   IDLE ──send──▶ THINKING ──response──▶ PROPOSING       │
                      │                     │           │
                      │                     ▼           │
                      │                  EXECUTING      │
                      │                     │           │
                      │                     ▼           │
                      │                  VERIFYING       │
                      │                  │      │       │
                      │                  ▼      ▼       │
                      │               SUCCESS  ERROR ────┘
                      └─empty/error──▶ ERROR
```

Rendering: a coloured dot plus a label (`Ready`, `Thinking…`, `Verifying…`, …). Transitions are
timer-driven — `QTimer.singleShot(2000/3000, lambda: set_state(IDLE))` — so the panel always
self-recovers even if no code path resets the state.

`refresh_last_message()` (`chat_ui.py:1446`) implements the two-phase reveal: the assistant message
is added *without* verification, then after execution and verification the widget is destroyed and
rebuilt with results attached. This is how the user sees plan → execute → verify progress in one
bubble.

---

## 8. Test Architecture

101 tests, six files, zero Slicer dependency.

### The import shim

`conftest.py` solves a packaging problem without a `setup.py`:

```python
sys.path.insert(0, ".../SlicerAICopilot")     # module dir on path
import SlicerAICopilotLib
sys.modules['SlicerAICopilot'] = SlicerAICopilotLib   # alias for relative imports
```

Slicer's module loader imports the folder as `SlicerAICopilot` (making `SlicerAICopilotLib` a
subpackage), whereas pytest imports the directory directly. The alias reconciles the two.

> ⚠️ `conftest.py` swallows every import exception with `except Exception: pass` (line 24). A typo in
> a submodule name would silently produce missing-attribute errors far from the cause. A `pytest.warn`
> or recorded failure would diagnose this in seconds.

### Coverage map

| File | Tests | Depth |
| ---- | ----- | ----- |
| `test_validator.py` | allowlist, bounds, unknown targets, malicious patterns | Good |
| `test_action_engine.py` | every verb, ambiguity, not-found | Good |
| `test_scene_manager.py` | enumeration, lookup, visibility/opacity | Good |
| `test_verification.py` | assertions, tolerances | Good |
| `test_file_manager.py` | extension + magic bytes, recursion, grouping | Good |
| `test_llm_client.py` | provider config, parsing, streaming, availability | Good |

**What is not covered:** `chat_ui.py` (1,462 LOC, the largest file, effectively untested),
`process_user_command()` in `SlicerAICopilot.py`, and `check_for_malicious_content()`'s integration
into the pipeline (it is tested in isolation but never called).

### Baseline

```text
$ python -m pytest tests/ -q
101 passed
```

> On a machine without `openai` installed, seven `test_llm_client.py` tests fail with
> `TypeError: 'NoneType' object is not callable` — the tests patch `OPENAI_AVAILABLE = True` but the
> module-level `OpenAI` symbol is `None`. Inside Slicer this is a non-issue because the module
> auto-installs `openai` on load. `pip install -r requirements.txt` resolves it locally.

---

## 9. Duplication and Divergence

The codebase grew a second orchestration path alongside the first. Both are live.

| Concern | `SlicerAICopilotLogic` | `chat_ui` |
| ------- | ---------------------- | --------- |
| `process_user_command` | `SlicerAICopilot.py:228` | `process_user_message` — `chat_ui.py:1265` |
| Prompt loading | `load_prompt()` — `:188` | `load_system_prompt()` — `:703` |
| Path resolution | `_resolve_prompt_path` — `:176` | `_resolve_prompt_path` — `:691` |
| Example loading | `_load_examples()` — `:210` | `_load_examples()` — `:725` |
| Scene formatting | inlined — `:242` | inlined — `:1283` |
| DICOM loading | `file_manager._load_dicom_folder` — `file_manager.py:180` | **duplicate** `_load_dicom_folder` — `chat_ui.py:1100` |
| `response_format` | ✅ `{"type":"json_object"}` — `:271` | ❌ not sent |

Consequences:

1. **Two copies of DICOM import logic** that must be kept in sync manually.
2. **`response_format` is inconsistent.** The logic path requests JSON mode; the chat path — the one
   users actually interact with — does not. This is likely a direct cause of the *"Invalid JSON from
   LLM"* troubleshooting entry.
3. **Bug containment is good.** Divergence means a defect in one path does not silently corrupt the
   other.

The clean fix is to make `SlicerAICopilotLogic` the single orchestrator and have `chat_ui` call it,
leaving the UI responsible only for rendering.

### The eightfold target-resolution prelude

`action_engine.py` repeats this block in `_execute_show`, `_execute_hide`, `_execute_show_only`,
`_execute_set_opacity`, `_execute_set_color`, `_execute_reset_display`, and `_execute_zoom_to`
(lines 93–101, 110–119, 137–145, 159–167, 177–185, 195–203, 226–234):

```python
node = self.scene_manager.find_node_by_name(target_name)
if not node:
    matches = self.scene_manager.find_matching_targets(target_name)
    if len(matches) == 1:   node = self.scene_manager.find_node_by_name(matches[0])
    elif len(matches) > 1:  return ActionResult(False, f"Ambiguous target '{target_name}'. Matches: {matches}")
    else:                   return ActionResult(False, f"Object '{target_name}' not found in scene")
```

~90 duplicated lines. This is the exact logic that belongs in `SceneManager.resolve_node()`, and
ironically it is **more correct than the validator's version of the same decision**.

---

## 10. Known Issues and Limitations

Ranked by impact. Nothing here is a security hole — the allowlist holds — but several are real
correctness or UX defects.

### 🔴 1. Ambiguous targets are silently resolved — `validator.py:86–93`

```python
if not self._target_exists(target):
    matches = self.scene_manager.find_matching_targets(target)
    if matches:
        action.target = matches[0]      # ← first match, no ambiguity check
```

`AGENTS.md` §22 mandates: *"If the scene contains Tumor 1/2/3 and the user says 'Hide the tumor',
do not arbitrarily select one. Ask which one."*

Because the target is rewritten to an exact node name, `action_engine`'s correct ambiguity check can
never fire. **Proposed fix** — mirror the engine's behaviour and return a disambiguation error:

```python
matches = self.scene_manager.find_matching_targets(target)
if len(matches) == 1:
    action.target = matches[0]
elif len(matches) > 1:
    errors.append(
        f"Target '{target}' is ambiguous. Candidates: {matches}. Ask the user which one."
    )
else:
    errors.append(f"Target '{target}' not found in scene")
```

### 🔴 2. Synchronous LLM call blocks the Slicer UI — `chat_ui.py:1333`

`llm_client.complete()` runs on the Qt main thread with a 120 s timeout. `QTimer.singleShot(0, …)`
lets the `THINKING` indicator paint first, but the freeze is real and total. Fix: `QThread` /
`QThreadPool` worker + a Qt signal for the result. `acomplete()` and `stream_complete()` already exist.

### 🟠 3. Empty action plans are rejected — `validator.py:37–39`

```python
if not plan.actions:
    errors.append("Action plan contains no actions")
    return False, errors
```

A conversational turn — *"hello"*, *"what can you do?"*, *"thanks"* — legitimately produces
`"actions": []`. The user sees `Validation failed: Action plan contains no actions` instead of an
answer. Proposed fix: return `(True, [])` for empty plans so `reply` is displayed without executing
anything, or have the model emit a `NO_ACTION` type.

### 🟠 4. The user message is sent twice — `chat_ui.py:1266` vs `:1313`

The message is appended to `self.conversation` at line 1266, then `self.conversation[-6:]` is
iterated at line 1299 (which includes it), then `text` is appended again at line 1313. The model
receives the command twice per turn. Fix: capture history *before* appending the new message.

### 🟠 5. `slicer.util.loadDICOM` does not exist — `action_engine.py:356`

```python
loaded_nodes = slicer.util.loadDICOM(action.path)   # AttributeError → caught → "DICOM import failed"
```

There is no `loadDICOM` in `slicer.util`. The supported path is `DICOMLib.DICOMUtils`:

```python
from DICOMLib import DICOMUtils
with DICOMUtils.TemporaryDICOMDatabase() as db:
    DICOMUtils.importDicom(path, db)
    for patientUID in db.patients():
        DICOMUtils.loadPatientByUID(patientUID)
```

`IMPORT_DICOM` is currently non-functional. Note that `file_manager._load_dicom_folder()` — used by
drag-and-drop — uses the correct plugin-logic approach, so the import feature itself works; only
this one action verb is broken.

### 🟠 6. `check_for_malicious_content()` is never called — `validator.py:163`

Unit-tested but dead. Either call it inside `handle_llm_response` before `json.loads`, or delete it.
Dead safety code is worse than none — it reads as protection that is not running.

### 🟡 7. Prompt/schema coverage gap

`ALLOWED_ACTIONS` contains 19 entries, but `system_prompt.txt` and `action_prompt.txt` document only
14. The five file-I/O verbs — `OPEN_FOLDER`, `IMPORT_DICOM`, `LOAD_VOLUME`, `LOAD_MODEL`,
`LOAD_SEGMENTATION` — are **never mentioned to the model**, so it cannot emit them. They are
unreachable through the chat path by omission.

This also means **the model-supplied `path` field is never validated against anything**: there is no
path traversal check, no allowlist of import roots, no extension check. If these verbs are ever
exposed to the model, `validator.py` must first constrain `path` to a user-approved root — today the
`OPEN_FOLDER` verb would forward an arbitrary model-supplied string into `os.walk`.

### 🟡 8. Only the first 8 of 15 few-shot examples load — `chat_ui.py:735`, `SlicerAICopilot.py:221`

`for ex in examples[:8]` hard-truncates. Examples 9–15 — including the valuable multi-action
"Prepare this case for review" — are unreachable. Fix: either raise the cap or select explicitly by
id/tag.

### 🟡 9. `fuzzy_match` over-matches — `utils.py:19–22`

Two problems in the substring branch:

```python
elif query_lower in candidate_lower or candidate_lower in query_lower:
```

(a) **No length floor.** A one-character query matches any candidate containing that character.
(b) **Bidirectional** — `candidate_lower in query_lower` means a long descriptive query matches a
short name, producing many false candidates that then feed the validator's `matches[0]`.

And `query_lower.replace("the", "")` strips `"the"` *anywhere*, so `"theatre"` → `"atre"` and
`"breath"` → `"brea"`. It should strip only a leading article:

```python
q = re.sub(r"^the\s+", "", query_lower)
```

### 🟡 10. Two broken magic-byte checks — `utils.py:76–80`

```python
if header[:3] == b'\x1f\x8b\x08':
    return "NIfTI"          # (a) matches ANY gzip file, not just NIfTI

if header[:4] in (b'<?xml', b'<VTK'):   # (b) header[:4] is 4 bytes, b'<?xml' is 5
    return "MODEL"          #     → can never be True
```

(a) classifies every gzipped archive (`.tar.gz`, `.json.gz`) as NIfTI. (b) is a constant-length
mismatch that silently never matches. Both need fixing; the compressed-NIfTI check should verify
gzip **and** decompress the first bytes to look for `n+1\0` (348-byte header magic).

### 🟡 11. `ZOOM_TO` and view verification is unconditional — `verification.py:287–318`

`_verify_zoom_to` returns `passed=True` without inspecting anything, with the message
`"executed (camera state not verifiable)"`. A green ✓ means *the function returned*, not *the camera
framed the object*. Fix: read back `renderer.GetActiveCamera().GetFocalPoint()` and compare against
the node's RAS bounds centre.

### 🟢 12. `verify_plan` silently drops unexecuted actions — `verification.py:323`

`zip(plan_actions, action_results)` truncates to the shorter sequence. When `execute_plan`
fail-fast-breaks after action 2 of 5, verification reports 2 results and the user is never told
actions 3–5 never ran.

### 🟢 13. Transform visibility is hardcoded — `scene_manager.py:145`

`vtkMRMLTransformNode` has no display node; `visible=True` is reported unconditionally and relayed
to the model as fact.

### 🟢 14. Plaintext API key on disk — `chat_ui.py:810–814`

`~/.slicer_ai_copilot/settings.json` stores the key unencrypted, world-readable by default on
POSIX. Acceptable for a desktop prototype; on a shared clinical workstation, prefer environment
variables and `chmod 600`.

### 🟢 15. Unused imports

`validator.py:3` (`Any`), `scene_manager.py:12` (`Dict, Any`), `action_engine.py:12`
(`Dict, Optional, Tuple`), `schemas.py:3` (`field_validator`). Harmless, but they obscure which
symbols are genuinely required.

---

## 11. Architectural Assessment

### What is genuinely well-built

1. **The one-way dependency graph.** `llm_client` has no import path to `action_engine`. The safety
   model is a structural property of the imports, not a runtime check someone can forget.
2. **Guarded Slicer imports.** Enables real unit testing on bare Python — the reason 101 tests can
   exist at all.
3. **Fail-closed throughout.** Parse errors, validation errors, execution errors, and LLM errors all
   halt the pipeline and surface to the user. No silent partial application.
4. **Fresh scene state by construction.** No cache means no staleness class of bug.
5. **Error swallowing at the UI boundary.** Nothing propagates into Qt's event loop.
6. **Generic, not demo-specific.** No `if "liver" in target` anywhere. The liver case is data, not
   code.

### What would most improve it

| Priority | Change | Effort | Impact |
| -------- | ------ | ------ | ------ |
| 1 | Move LLM call to a worker thread | Medium | Eliminates UI freeze |
| 2 | Fix ambiguity handling in the validator | Small | Restores a documented safety guarantee |
| 3 | Allow empty action plans | Small | Fixes conversational turns |
| 4 | Fix duplicated user message | Trivial | Correctness of every request |
| 5 | Consolidate orchestration into `Logic` | Medium | Removes duplication + drift |
| 6 | Constrain `path` on file-I/O actions | Small | Required before exposing those verbs |
| 7 | Real camera verification | Medium | Makes ZOOM_TO evidence real |
| 8 | Harden `fuzzy_match` | Small | Fewer wrong-target matches |
| 9 | Fix magic-byte detection | Small | Correct file classification |
| 10 | Delete or wire up `check_for_malicious_content` | Trivial | Removes misleading dead code |

### Test debt

`chat_ui.py` — 1,462 LOC, the largest and most stateful file — has no tests. The 1,462-line class
would benefit most from extracting the pure logic (state transitions, message-stack construction,
plan formatting) into testable functions, leaving Qt wiring thin.

---

## 12. Specification Conformance

| `AGENTS.md` requirement | Status | Evidence |
| ------------------------ | ------ | -------- |
| Embedded Slicer module, no browser | ✅ | `ScriptedLoadableModule` + Qt widget |
| LLM never executes Python | ✅ | No `exec`/`eval`; JSON + Pydantic only |
| Strict action allowlist | ✅ | `ALLOWED_ACTIONS`, 19 entries |
| Validate before execute | ✅ | `validator.validate_plan` gates the engine |
| Verify after execute | ⚠️ Partial | Works for display ops; `ZOOM_TO` is a no-op |
| Targets grounded in the real scene | ✅ | `find_node_by_name` + fuzzy fallback |
| Ambiguity triggers clarification | ❌ | Validator takes `matches[0]` |
| Fresh scene context every turn | ✅ | No caching; `get_scene_summary()` per request |
| Conversation memory, scene authoritative | ✅ | History replayed, never trusted |
| Folder drop with format detection | ✅ | Extension + magic bytes |
| DICOM series grouping | ⚠️ Partial | By directory, not `SeriesInstanceUID` |
| Tests for each action type | ✅ | 101 tests across 6 files |
| Generic, not liver-specific | ✅ | Zero anatomy-specific branching |
| No destructive operations | ✅ | No `DELETE`/`CLEAR_SCENE`/`SAVE` verbs |
| Non-blocking LLM inference | ❌ | Synchronous call on the Qt main thread |
| Medical disclaimers in the prompt | ✅ | `system_prompt.txt` |
| API keys out of source | ✅ | Env vars + external settings file |

**14 of 17 fully met, 2 partial, 3 gaps** — the gaps being async inference, ambiguity handling, and
conversation-only turns.

---

<div align="center"><sub>Next: [AI_INTEGRATION.md](AI_INTEGRATION.md) · [architecture.md](architecture.md) · [demo.md](demo.md)</sub></div>