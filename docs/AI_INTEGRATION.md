# AI Integration — Deep Dive

This document dissects the LLM layer: what we send, what we expect back, how the contract is
enforced, and where the current implementation leaks. Companion reading:
[architecture.md](architecture.md) and [REVERSE_ENGINEERING.md](REVERSE_ENGINEERING.md).

---

## 1. Design Principle

> **The model chooses the intent. Our code owns the execution.**

A conventional "chat with your data" agent gives an LLM a Python interpreter and hopes. We invert it.
The model's output is a **declarative plan** — data, not code — that must survive four independent
gates before a single MRML node changes:

```text
        ┌─────────────────────────────────────────────┐
  G1    │ JSON parse            (json.loads)          │  syntax
        ├─────────────────────────────────────────────┤
  G2    │ Schema validation     (Pydantic union)     │  shape + types + ranges
        ├─────────────────────────────────────────────┤
  G3    │ Policy validation     (validator.py)       │  allowlist + scene grounding
        ├─────────────────────────────────────────────┤
  G4    │ Post-hoc verification (verification.py)    │  did reality match the plan?
        └─────────────────────────────────────────────┘
```

G4 is what makes this project different from a chatbot: it does not ask the model whether it
succeeded. It asks MRML.

---

## 2. The Transport Layer — `llm_client.py`

### Provider abstraction

Every supported provider exposes an OpenAI-compatible `/chat/completions` endpoint, so one client
covers all of them:

```python
PROVIDER_CONFIGS = {
    "modelscope": {"base_url": "https://api-inference.modelscope.ai/v1",
                   "model": "Qwen/Qwen3.5-9B"},
    "gemini":     {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                   "model": "gemini-2.5-flash"},
    "openai":     {"base_url": "https://api.openai.com/v1",
                   "model": "gpt-4o"},
}
```

Resolution order for each setting is **explicit argument → environment variable → provider default**:

```python
self.provider = provider or os.getenv("LLM_PROVIDER", "gemini")
self.api_key  = api_key  or os.getenv("LLM_API_KEY")
self.base_url = base_url or os.getenv("LLM_BASE_URL", config.get("base_url", ""))
self.model    = model    or os.getenv("LLM_MODEL",    config.get("model", ""))
```

Because precedence is argument-first, the settings panel can reconfigure a live client without
restarting Slicer — it reassigns attributes and calls `_init_clients()` again.

### Call surface

| Method | Async | Streaming | Used by |
| ------ | ----- | --------- | ------- |
| `complete()` | No | Optional | **Both** orchestration paths (primary) |
| `acomplete()` | Yes | Optional | Nothing currently |
| `stream_complete()` | No | Yes (generator) | Nothing currently |
| `_parse_response()` | — | — | Non-streaming responses |
| `_handle_stream()` / `_handle_stream_async()` | — | Yes | Chunk accumulation |

Two response-only fields are captured for observability:

- **`reasoning_content`** — extended-thinking output from reasoning models, surfaced separately from
  `content` so chain-of-thought never contaminates the JSON payload.
- **`usage`** — prompt / completion / total token counts, captured for cost tracking.

### Failure behaviour

Every failure path returns an **empty `LLMResponse` with `finish_reason="error"`** rather than
raising:

```python
except Exception as e:
    logger.error(f"LLM completion failed: {e}")
    return LLMResponse(content="", finish_reason="error", usage=None)
```

This is deliberate. An exception escaping into Qt's event loop would tear down the Slicer UI. Instead
`chat_ui.handle_llm_error()` renders *"AI error: … You can still use manual Slicer controls"* and the
copilot returns to `IDLE`. The philosophy is that a failed AI must never degrade Slicer itself.

### Credential handling

```text
Environment variable  LLM_API_KEY
        │
        ├── fallback ──▶ ~/.slicer_ai_copilot/settings.json   (written by the settings panel)
        │
        └── never ─────▶ source code, git, logs, scene data
```

> 🔒 The settings file is plaintext in the user's home directory. It is never uploaded and is not
> in the repository. See [REVERSE_ENGINEERING.md §6](REVERSE_ENGINEERING.md#6-known-issues-and-limitations).

---

## 3. Prompt Construction

### The message stack

Built in `chat_ui.process_user_message()` (lines 1291–1313):

```text
[system]    system_prompt.txt            role + safety contract + allowed actions
[system]    "Current Slicer scene:\n…"   live MRML dump (refreshed every turn)
  [user]      few-shot example 1         ┐
[assistant]   example 1 JSON plan        │ up to 8, from
  [user]      few-shot example 2         │ knowledge/slicer_examples.json
[assistant]   example 2 JSON plan        ┘
  …
  [user]      recent turn                ┐ pruned conversation history,
[assistant]   recent turn                │ last 6 messages, rebuilt each
  …                                       ┘ turn from the local transcript
[system]    action_prompt.txt           exact JSON schema + rules + examples
[user]      "Hide the skin"             the actual command
```

**Why this order?**

1. **Identity first** — the safety contract must be established before any scene data appears, so
   scene text is untrusted content read *under* the rules, not content that defines them.
2. **Scene before request** — the model needs the facts before it can plan, and putting the scene in
   a `system` message (not a `user` message) reduces the chance of it being treated as the
   conversation subject.
3. **Output schema last** — instructions closest to the generation point carry the most weight, so
   the JSON contract sits immediately before the user turn.
4. **`temperature=0.1`** — near-deterministic. Planning a set of display operations has exactly one
   correct answer; creativity is a liability.

### The system prompt as a security contract

`prompts/system_prompt.txt` is not a personality. It is a threat model in prose:

```text
You are Slicer AI Copilot.
You control a 3D Slicer scene through a restricted action API.

Never output executable Python.
Never invent objects that are not present in the provided scene.
Never make a diagnosis or treatment recommendation.
Only use actions from the allowed action list.
If a requested object does not exist, report that clearly.
If a request is ambiguous, ask for clarification.
Return valid JSON only.
```

The clinical restrictions (`never diagnose`, `never recommend treatment`) are a **product** control,
not a technical one — nothing stops the model from emitting diagnostic prose into `reply`. They exist
to shape behaviour and because `AGENTS.md` §25 mandates it. Enforcement of *operational* limits,
by contrast, is entirely in code.

> 📌 Every restriction in that file that claims to be a guarantee ("only use actions from the
> allowed list", "never invent objects") is actually enforced by `validator.py`, not by the prompt.
> The prompt raises the floor; the validator sets the ceiling.

### Scene serialisation

`utils.format_scene_summary()` flattens the Pydantic `SceneSummary` into plain text:

```text
Models:
  - Liver (visible, opacity=0.3)
  - Tumor (visible)
  - Skin (hidden)
Volumes:
  - CT (visible)
Segmentations:
  - LiverSeg (visible)
```

Only `name`, `type`, `visible`, `opacity` are emitted. **No voxels, no DICOM tags, no patient
identifiers.** Sending *"Hide the skin"* transmits the literal string `Skin` and nothing else.

The scene is rebuilt from `get_scene_summary()` on **every single turn** — there is no caching layer,
so stale state is structurally impossible.

### Few-shot examples

`knowledge/slicer_examples.json` holds 15 curated examples; the loader takes the **first 8** to bound
token cost. They demonstrate:

- the mapping from colloquial phrasing → canonical action (`"Hide everything except the tumor"` →
  `SHOW_ONLY`),
- multi-action composition (`"Prepare this case for review"` → 5 chained actions),
- semantic conversions the model would otherwise get wrong (`"80%"` → `0.8`,
  `"transparent"` → `0.3`).

Because exactly 8 are loaded and the file has 15, **examples 9–15 are currently unreachable.**
Reordering the file changes behaviour — a real fragility noted in
[REVERSE_ENGINEERING.md §6](REVERSE_ENGINEERING.md#6-known-issues-and-limitations).

---

## 4. The Output Contract — `schemas.py`

### Discriminated union

Fourteen `Literal`-tagged Pydantic models form a union keyed on `type`:

```python
class SetOpacityAction(ActionBase):
    type: Literal["SET_OPACITY"]
    target: str
    value: float = Field(ge=0.0, le=1.0)      # ← range enforced at parse time
```

Pydantic tries each member in order and keeps the one whose discriminator matches. An action with a
valid `type` but malformed fields fails to parse **before** validation is ever called.

### Action vocabulary

| Category | Actions |
| -------- | ------- |
| Visibility | `SHOW`, `HIDE`, `SHOW_ONLY` |
| Display | `SET_OPACITY`, `SET_COLOR`, `RESET_DISPLAY` |
| Camera | `RESET_VIEW`, `ZOOM_TO`, `THREE_D_VIEW`, `AXIAL_VIEW`, `SAGITTAL_VIEW`, `CORONAL_VIEW` |
| Inspection | `LIST_OBJECTS`, `LIST_VISIBLE_OBJECTS` |
| File I/O | `OPEN_FOLDER`, `IMPORT_DICOM`, `LOAD_VOLUME`, `LOAD_MODEL`, `LOAD_SEGMENTATION` |

`ALLOWED_ACTIONS` is the authoritative set; `ACTION_CLASSES` maps each name to its model.

> ⚠️ The file-I/O actions exist in the schema and the validator but are **absent from the system
> prompt**, so the model is never told about them. They are currently unreachable via the chat path.
> See [REVERSE_ENGINEERING.md §5](REVERSE_ENGINEERING.md#5-schema-vs-prompt-coverage-gap).

---

## 5. Validation — `validator.py`

The mandatory safety boundary. Five checks, in order:

```text
1. type ∈ ALLOWED_ACTIONS        ── closed-world allowlist
2. type ∈ ACTION_CLASSES         ── a validator exists for it
3. target resolves in MRML       ── scene grounding (exact, then fuzzy)
4. 0.0 ≤ value ≤ 1.0             ── parameter bounds (redundant with Pydantic, kept deliberately)
5. len(color) == 3, each 0.0–1.0 ── parameter shape
```

Checks 4 and 5 duplicate schema constraints. That is intentional: the schema is data validation, the
validator is a **policy** layer. If someone loosens the Pydantic field, the policy layer still holds.

### Target resolution and its failure mode

`_validate_single_target()` implements the scene-grounding step:

```python
if not self._target_exists(target):
    matches = self.scene_manager.find_matching_targets(target)
    if matches:
        action.target = matches[0]      # ← takes the first match unconditionally
    else:
        errors.append(f"Target '{target}' not found in scene")
```

The intended behaviour (per `AGENTS.md` §22) is to refuse ambiguous targets. The implementation
instead **takes `matches[0]` and proceeds**, so `"Hide the tumor"` against `Tumor 1/2/3` silently
picks `Tumor 1`. Because the name is rewritten to an exact match, the action engine's ambiguity
check never fires — the safety net downstream is bypassed by the layer upstream.

> 🔴 This is the most consequential finding in the codebase. Documented in full, with the proposed
> fix, in [REVERSE_ENGINEERING.md §6](REVERSE_ENGINEERING.md#6-known-issues-and-limitations).

`check_for_malicious_content()` — a blocklist scanner for `exec(`, `eval(`, `__import__`,
`subprocess`, `__subclasses__` and friends — exists and is unit-tested but is **never invoked by the
runtime pipeline**. It is dead defence-in-depth.

---

## 6. Execution — `action_engine.py`

The only module permitted to mutate the scene. Dispatch is a flat `if/elif` on `action.type`, each
branch delegating to a typed, hand-written method:

```python
{"type": "HIDE", "target": "Skin"}
        │
        ▼
ActionEngine._execute_hide(HideAction)      ← our code, not the model's
        │
        ▼
SceneManager.set_visibility(node, False)    ← MRML display node
```

Each `_execute_*` method repeats the same defensive prelude:

```python
node = self.scene_manager.find_node_by_name(target_name)
if not node:
    matches = self.scene_manager.find_matching_targets(target_name)
    if len(matches) == 1:   node = self.scene_manager.find_node_by_name(matches[0])
    elif len(matches) > 1:  return ActionResult(False, f"Ambiguous target '{target_name}'. Matches: {matches}")
    else:                   return ActionResult(False, f"Object '{target_name}' not found in scene")
```

**This is the correct behaviour the validator should have.** The engine handles ambiguity properly —
it is simply never given the chance, because the validator has already rewritten the target to an
exact name. The redundancy is also why `action_engine.py` repeats the prelude eight times; a shared
`_resolve_target_or_fail()` helper would be the obvious refactor.

### Plan semantics

```python
for action in plan.actions:
    result = self.execute_action(action)
    results.append(result)
    if not result.success:
        break        # fail-fast: abort the remaining plan
```

The engine stops at the first failure. Combined with `verify_plan()`'s `zip(plan_actions,
action_results)`, unexecuted actions simply do not appear in verification output — the user sees a
short result list, not an error about the actions that never ran.

---

## 7. Verification — `verification.py`

The closing argument. For every successfully executed action, the scene is re-read and compared
against intent:

| Action | Assertion |
| ------ | --------- |
| `SHOW` / `HIDE` | `display_node.GetVisibility()` matches intent |
| `SHOW_ONLY` | every target visible **and** zero non-targets visible |
| `SET_OPACITY` | `\|actual − expected\| < 0.05` |
| `SET_COLOR` | per-channel `\|actual − expected\| < 0.05` |
| `RESET_DISPLAY` | visible and opacity ≈ 1.0 |
| `ZOOM_TO` / view actions | reports "executed" — **not verifiable** (see below) |

A 0.05 tolerance absorbs the float rounding that occurs when opacity round-trips through VTK.

```text
User:  "Hide the skin"

Plan:     HIDE → Skin
Execute:  Skin.hidden = true
Verify:   read Skin.hidden → true
Render:   ✓ Skin is hidden
```

### Honest limitations

- **`ZOOM_TO` and view switching are unverifiable.** `_verify_zoom_to` returns `passed=True`
  unconditionally with the message `"executed (camera state not verifiable)"`. A green checkmark
  there means *the function returned*, not *the camera framed the object*. Camera state is not
  queryable through the MRML display-node API used here, so closing this gap needs a different
  verification mechanism — e.g. reading back `renderer.GetActiveCamera().GetFocalPoint()` and
  comparing against the node's RAS bounds centre.
- **Verification is not independent.** `scene_manager` both writes and reads the scene, so a bug in
  the write path and its mirror in the read path would agree with each other and produce a false
  pass. Truly independent verification would read through a different path (raw VTK / the Slicer
  console's own state report).

---

## 8. Conversation Memory

Pruned to the last 6 transcript entries and rebuilt from the local widget state each turn:

```python
for msg in self.conversation[-6:]:
    if msg.role == "user":
        messages.append({"role": "user", "content": msg.content})
    elif msg.role == "assistant":
        if msg.action_plan:
            plan_summary = json.dumps({"reply": ..., "actions": [...]})
            messages.append({"role": "assistant", "content": plan_summary})
        elif msg.content:
            messages.append({"role": "assistant", "content": msg.content})
```

Design properties, both correct per `AGENTS.md`:

- **The scene always wins.** History is advisory; `get_scene_summary()` runs fresh every turn. A
  hallucinated name in an old assistant message cannot make an object "exist".
- **History is replayed, not trusted.** Plans are re-serialised from the Pydantic objects each time,
  so the transcript cannot drift into unparseable shape.

> ⚠️ The current user's message is appended to `self.conversation` at line 1266 *before* the
> history loop, and then appended again at line 1313 — so it is sent twice. See
> [REVERSE_ENGINEERING.md §6](REVERSE_ENGINEERING.md#6-known-issues-and-limitations).

---

## 9. Threading and Responsiveness

The call is **synchronous on the Qt main thread**:

```python
self.set_state(UIState.THINKING)
QTimer.singleShot(0, lambda: self.call_llm(messages))
#  → call_llm → self.llm_client.complete(...)   ← blocks the event loop
```

`QTimer.singleShot(0, …)` lets the status indicator repaint to `THINKING…` before the block begins —
so the UI *looks* responsive — but any request longer than a few hundred milliseconds freezes
Slicer entirely: no panning, no module switching, no window drag. With a 120-second timeout, a slow
or unreachable provider produces a two-minute freeze.

`llm_client.py` already ships the primitives for a fix — `acomplete()` and `stream_complete()` — and
`AGENTS.md` §38 anticipates a separate inference process. The missing piece is moving the call onto
a `QThread`/`QThreadPool` worker and marshalling the result back with a Qt signal.

This is the single highest-impact improvement available to the project.

---

## 10. Privacy

| Data | Sent to provider? | Rationale |
| ---- | ----------------- | --------- |
| Node names, types | ✅ Yes | Required for the model to address objects |
| Visibility, opacity, colour | ✅ Yes | Required to answer *"what is visible?"* |
| Voxel / image data | ❌ **Never** | Irrelevant to scene control |
| DICOM tags, patient name, accession | ❌ **Never** | Not collected by `scene_manager` |
| API key | ❌ Never | Sent only to the provider's auth endpoint |

`SceneObject` (`schemas.py`) is the entire outbound surface: `name`, `type`, `visible`, `opacity`,
`color`. There is no field capable of carrying pixel data, because no code ever populates one.

> ⚠️ Operators must still confirm their institution's policy: node names can carry PHI
> (e.g. a series named `DOE_JOHN_Q_2024_CT`). Rename or use anonymised data before use.

---

## 11. Summary

| Concern | Mechanism | Enforced in |
| ------- | --------- | ----------- |
| Model emits Python | No Python sink exists anywhere in the pipeline | Architecture |
| Unknown action type | `ALLOWED_ACTIONS` + Pydantic union | `schemas.py` |
| Malformed parameters | `Field(ge/le)` + explicit bounds checks | `schemas.py` + `validator.py` |
| Non-existent target | Exact → fuzzy MRML resolution | `validator.py` |
| Ambiguous target | **Intended but broken** — takes `matches[0]` | `validator.py` ⚠️ |
| Plan over-reach | Not possible — no destructive verbs exist | Allowlist design |
| False success claims | Scene re-read and compared to intent | `verification.py` |
| Partial execution | Fail-fast `break` on first failure | `action_engine.py` |
| UI freeze | **Not handled** — synchronous call on main thread | ⚠️ |
| Data leakage | Metadata-only serialisation | `scene_manager.py` + `schemas.py` |

---

## 12. Possible Improvements

1. **Worker thread** — move `complete()` off the Qt event loop. Highest impact.
2. **Allow empty plans** — a conversational turn ("hello", "what can you do?") currently produces a
   validation error instead of an answer.
3. **Surface ambiguity as a question** — return the candidate list to the user and let them pick,
   rather than guessing or failing.
4. **Wire up `check_for_malicious_content()`** — or delete it. Dead safety code is a liability: it
   reads as protection that is not running.
5. **Real camera verification** — read back focal point vs. node RAS bounds for `ZOOM_TO`.
6. **Streaming UI** — render tokens as they arrive behind a "composing plan…" indicator.
7. **Token accounting** — `usage` is already captured; surface it in the status bar.
8. **Prompt/knowledge single-sourcing** — generate both the prompt text and `knowledge/*.json` from
   one definition so they cannot drift.

---

<div align="center"><sub>Next: [architecture.md](architecture.md) · [REVERSE_ENGINEERING.md](REVERSE_ENGINEERING.md) · [demo.md](demo.md)</sub></div>