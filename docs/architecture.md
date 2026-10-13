# Architecture

Slicer AI Copilot is a natural-language AI assistant embedded directly inside 3D Slicer.

For a component-by-component code analysis, see
[REVERSE_ENGINEERING.md](REVERSE_ENGINEERING.md).
For the LLM layer in depth, see [AI_INTEGRATION.md](AI_INTEGRATION.md).

---

## Pipeline

```text
User Input (chat_ui.py)
    → LLM (llm_client.py via any OpenAI-compatible provider)
    → JSON Response Parsing
    → Schema Validation (schemas.py — Pydantic union)
    → Policy Validation (validator.py) — safety boundary
    → Action Execution (action_engine.py)
    → Scene Modification (scene_manager.py → Slicer API)
    → Verification (verification.py)
    → UI Feedback (chat_ui.py)
```

```text
┌──────────────────────────────────────────────────────────┐
│                       3D SLICER                          │
│                                                          │
│  ┌───────────────────────┐    ┌────────────────────────┐  │
│  │    AI COPILOT UI      │    │      MRML SCENE       │  │
│  │  chat / DnD / status  │    │  volumes, models,     │  │
│  │                       │    │  segmentations,       │  │
│  └───────────┬───────────┘    │  markups, transforms  │  │
│              │                └───────────┬────────────┘  │
└──────────────┼────────────────────────────┼───────────────┘
               │                            │
               ▼                            ▼
      ┌─────────────────┐          ┌──────────────────┐
      │  llm_client.py  │          │  scene_manager   │
      │ OpenAI-compat   │          │  MRML read/write │
      └────────┬────────┘          └──────────────────┘
               │ structured JSON (never code)
               ▼
      ┌─────────────────┐
      │   schemas.py    │  14 action types, ALLOWED_ACTIONS
      └────────┬────────┘
               ▼
      ┌─────────────────┐
      │  validator.py   │  ◀── SAFETY BOUNDARY
      └────────┬────────┘
               ▼
      ┌─────────────────┐
      │  action_engine  │  ◀── ONLY layer allowed to mutate the scene
      └────────┬────────┘
               ▼
      ┌─────────────────┐
      │ verification.py │  ◀── re-reads MRML, reports ✓ / ✗
      └─────────────────┘
```

---

## Layer Contract

| Layer | File | May modify the scene? | May call the LLM? |
| ----- | ---- | :-------------------: | :---------------: |
| UI | `chat_ui.py` | No | Passes messages only |
| Transport | `llm_client.py` | **Never** | ✅ only this layer |
| Contract | `schemas.py` | No | No |
| Policy | `validator.py` | No (may annotate targets) | No |
| Execution | `action_engine.py` | ✅ | No |
| Evidence | `verification.py` | Read-only | No |
| Files | `file_manager.py` | Via `slicer.util` | No |

This one-way dependency direction is what makes the safety model hold: **there is no code path from
model output to scene mutation that skips the validator.**

---

## Components

### `SlicerAICopilot.py`

Module entry point following Slicer's `Module` / `Widget` / `Logic` triad.

- Registers the module (`title`, `categories`, `helpText`) and sets the icon.
- Bootstraps runtime dependencies — auto-installs `openai` and `pydantic` via
  `slicer.util.pip_install()` if missing (guarded, degrades to a warning).
- `SlicerAICopilotLogic` assembles all six singletons and exposes prompt/knowledge loading plus
  `process_user_command()`.
- `onSceneStartClose` clears the pending plan and conversation so a stale plan cannot execute against a
  replaced scene.

### `chat_ui.py`

Qt-based chat panel. Owns message rendering, drag-and-drop, the settings panel, the status indicator,
and the UI state machine.

**State machine** — `IDLE → THINKING → PROPOSING → EXECUTING → VERIFYING → SUCCESS | ERROR`, with
timer-driven self-recovery to `IDLE`.

**Two-phase message reveal** — the assistant bubble is added after parsing (showing the plan), then
destroyed and rebuilt with verification results attached, so plan → execute → verify is visible within
a single message.

Slicer imports are guarded, so the module degrades gracefully outside Slicer and remains importable by
the test suite.

### `llm_client.py`

OpenAI-compatible transport. One `OpenAI` client with a swappable `base_url` covers ModelScope,
Gemini, OpenAI, and any compatible endpoint.

- Settings resolve **argument → environment variable → provider default**.
- Exposes `complete()` (sync), `acomplete()` (async), and `stream_complete()` (generator).
- Captures `reasoning_content` separately from `content` so chain-of-thought never contaminates JSON.
- **Never raises** — every failure returns an empty `LLMResponse` with `finish_reason="error"`, so a
  failing AI cannot tear down the Slicer UI.

Configured via `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`.

### `scene_manager.py`

The MRML boundary. Enumerates volumes, models, segmentations, markups and transforms; reads and writes
visibility, opacity and colour through each node's display node.

- `find_node_by_name()` — exact MRML lookup, returns `None` rather than raising when absent.
- `find_matching_targets()` — normalised substring matching over all object names.
- **No caching** — `get_scene_summary()` reads live state on every call, so stale scene context is
  structurally impossible.

### `schemas.py`

Pydantic contract. Fourteen `Literal`-tagged action models forming a discriminated union, plus
`ActionPlan`, `SceneObject`, `SceneSummary`, `ALLOWED_ACTIONS` and `ACTION_CLASSES`.

Field constraints are enforced at parse time — `SET_OPACITY.value` is `Field(ge=0.0, le=1.0)`,
`SET_COLOR.color` is exactly 3 components.

### `validator.py`

The mandatory safety boundary. Five checks:

1. action type ∈ `ALLOWED_ACTIONS`
2. a validator exists for that type
3. target resolves to a real MRML node (exact → fuzzy)
4. `0.0 ≤ value ≤ 1.0`
5. `len(color) == 3`, each component `0.0–1.0`

Checks 4 and 5 duplicate the schema constraints **deliberately**: the schema is data validation, the
validator is a policy layer, and loosening one must not silently loosen the other.

Also provides `check_for_malicious_content()`, a blocklist scanner for `exec(`, `eval(`,
`__import__`, `subprocess`, `__subclasses__` and similar. *(Currently defined and unit-tested but not
wired into the runtime pipeline — see
[REVERSE_ENGINEERING.md §10](REVERSE_ENGINEERING.md#6-known-issues-and-limitations).)*

### `action_engine.py`

The **only** layer permitted to mutate the Slicer scene. Flat `if/elif` dispatch on `action.type`,
each branch delegating to a hand-written `_execute_*` method that calls Slicer APIs.

Plan execution is **fail-fast** — the loop breaks on the first unsuccessful action, so a plan is never
silently half-applied.

File-I/O verbs (`IMPORT_DICOM`, `LOAD_VOLUME`, `LOAD_MODEL`, `LOAD_SEGMENTATION`, `OPEN_FOLDER`)
delegate to `slicer.util` or `file_manager`. *(Not exposed to the model via the current prompt — see
[REVERSE_ENGINEERING.md §10](REVERSE_ENGINEERING.md#6-known-issues-and-limitations).)*

### `verification.py`

Post-execution evidence. Re-reads the actual MRML scene and compares it against intent:

| Action | Assertion |
| ------ | --------- |
| `SHOW` / `HIDE` | `display_node.GetVisibility()` matches |
| `SHOW_ONLY` | all targets visible **and** zero non-targets visible |
| `SET_OPACITY` | `\|actual − expected\| < 0.05` |
| `SET_COLOR` | per-channel `\|actual − expected\| < 0.05` |
| `RESET_DISPLAY` | visible and opacity ≈ 1.0 |
| `ZOOM_TO`, view switches | reports *executed* — **not verifiable** |

The 0.05 tolerance absorbs float rounding when opacity round-trips through VTK.

### `file_manager.py`

Folder scanning and import.

- **Detection** — extension first, magic bytes as fallback (DICOM `DICM` at offset 128, NRRD magic,
  VTK header, gzip).
- **Grouping** — `group_dicom_series()` groups by parent directory.
- **Import** — delegates to Slicer, with a four-strategy DICOM fallback
  (`examineForLoad` → `loadDirectory` → crawler → `loadNodeFromFile`), each individually guarded so one
  unusual folder layout does not break the import.
- **User-confirmed** — the manager *detects*; `import_case()` runs only on explicit selection.

### `utils.py`

Dependency-free helpers.

- `fuzzy_match()` / `resolve_target()` / `find_matching_objects()` — name matching.
- `get_file_type()` / `_detect_by_content()` — format detection.
- `scan_folder_for_files()` / `group_dicom_series()` — recursive scanning.
- `format_scene_summary()` — flattens `SceneSummary` to the plain text sent to the model, emitting
  only `name`, `type`, `visible`, `opacity`, `color`. **No pixel data, no DICOM tags, no identifiers.**

---

## Data Contracts

### `SceneSummary` — the outbound payload

```python
class SceneSummary(BaseModel):
    volumes:      List[SceneObject]   # name, type, visible
    models:       List[SceneObject]   # name, type, visible, opacity, color
    segmentations: List[SceneObject]  # name, type, visible, opacity
    markups:      List[SceneObject]   # name, type, visible
    transforms:   List[SceneObject]   # name, type
```

Serialized to the model as:

```text
Models:
  - Liver (visible, opacity=0.3)
  - Tumor (visible)
  - Skin (hidden)
Volumes:
  - CT (visible)
```

This struct is the **entire** outbound surface. There is no field capable of carrying pixel data,
because no code populates one.

### `ActionPlan` — the inbound payload

```json
{
  "version": "1.0",
  "reply": "I'll hide the skin and show only the tumor.",
  "actions": [
    { "type": "HIDE", "target": "Skin" },
    { "type": "SHOW_ONLY", "targets": ["Tumor"] }
  ]
}
```

### `ActionResult` / `VerificationResult`

```text
ActionResult(success, message, data)            ← what the engine did
VerificationResult(action_type, target,
                    expected, actual,
                    passed, message)             ← what the scene says happened
```

---

## Action Vocabulary

| Category | Actions |
| -------- | ------- |
| Visibility | `SHOW`, `HIDE`, `SHOW_ONLY` |
| Display | `SET_OPACITY`, `SET_COLOR`, `RESET_DISPLAY` |
| Camera | `RESET_VIEW`, `ZOOM_TO`, `THREE_D_VIEW`, `AXIAL_VIEW`, `SAGITTAL_VIEW`, `CORONAL_VIEW` |
| Inspection | `LIST_OBJECTS`, `LIST_VISIBLE_OBJECTS` |
| File I/O | `OPEN_FOLDER`, `IMPORT_DICOM`, `LOAD_VOLUME`, `LOAD_MODEL`, `LOAD_SEGMENTATION` |

`ALLOWED_ACTIONS` holds all 19. The 14 visibility/display/camera/inspection actions are documented in
the prompts and reachable from chat; the 5 file-I/O actions are implemented but currently not exposed
to the model.

**Notably absent, by design:** `DELETE`, `CLEAR_SCENE`, `SAVE`, `EXPORT`, and anything that writes to
patient data. The worst a prompt injection can achieve is a visual tweak.

---

## Safety Model

```text
LLM = Understand and plan
    ↓
Validator = Decide what is allowed
    ↓
Action Engine = Execute trusted operations
    ↓
Slicer = Perform the actual work
    ↓
Verification = Confirm what actually happened
```

The LLM never receives unrestricted execution privileges. Every operation passes through a controlled
action layer and a verification step. **Never invert this relationship.**

Four independent gates stand between model output and scene mutation:

```text
G1  JSON parse          json.loads
G2  Schema validation   Pydantic union  (shape, types, ranges)
G3  Policy validation   validator.py    (allowlist, scene grounding)
G4  Post-hoc verification verification.py (does reality match the plan?)
```

---

## Configuration

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `LLM_PROVIDER` | No | `gemini` | `modelscope`, `gemini`, or `openai` |
| `LLM_API_KEY` | **Yes** | — | Provider API key |
| `LLM_BASE_URL` | No | per provider | Override the endpoint |
| `LLM_MODEL` | No | per provider | Override the model |

Persisted settings live in `~/.slicer_ai_copilot/settings.json` (plaintext, outside the repository).
See [AI_INTEGRATION.md §2](AI_INTEGRATION.md#2-the-transport-layer--llm_clientpy) and the
[Troubleshooting table](../README.md#-troubleshooting).

---

## Testing

101 tests run on plain CPython — no 3D Slicer required — because every Slicer import is guarded.

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

---

<div align="center"><sub>Next: [AI_INTEGRATION.md](AI_INTEGRATION.md) · [REVERSE_ENGINEERING.md](REVERSE_ENGINEERING.md) · [demo.md](demo.md)</sub></div>