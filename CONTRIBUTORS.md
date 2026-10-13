# Contributors

Thanks to everyone who has helped build **Slicer AI Copilot** — a natural-language control layer for
[3D Slicer](https://www.slicer.org/) that turns plain-English requests into validated, verified
operations on a medical-imaging scene.

This project follows the principle that **the model proposes intent; application code controls
execution**. Contributions that preserve that boundary are especially welcome.

---

## Core Team

### Juhaim Mohammed MT — Creator

[![GitHub](https://img.shields.io/badge/GitHub-Juhamim-181717?style=flat-square&logo=github)](https://github.com/Juhamim)

Original design and implementation of the module architecture, the layered safety model, and the
verification approach.

- Architecture and safety model — the validator boundary, action allowlist, post-execution verification
- Core engine — `action_engine.py`, `scene_manager.py`, `validator.py`, `verification.py`
- LLM integration — `llm_client.py` provider abstraction, prompt stack, scene serialisation
- Slicer module — `SlicerAICopilot.py`, drag-and-drop case import in `chat_ui.py`
- Test suite — 101 unit tests across 6 modules

### Haleema Nasmila — Co-Creator & Contributor

[![GitHub](https://img.shields.io/badge/GitHub-haleemanasmila-181717?style=flat-square&logo=github)](https://github.com/haleemanasmila)

Co-creator and ongoing contributor to the project.

- Project documentation and contributor programme — `CONTRIBUTORS.md`, README structure
- Documentation and onboarding — `docs/`, `Agents.md` guidance for new contributors
- Ongoing review, testing, and maintenance

---

## How Contributions Are Credited

| Role | Meaning |
| ---- | ------- |
| **Creator** | Original design and implementation of the architecture and safety model |
| **Co-Creator** | Sustained design and implementation partnership |
| **Contributor** | Code, documentation, testing, review, or project administration |

To be credited here, open a pull request and add yourself to this file and to the
[Creators & Contributors](README.md#-creators--contributors) section of the README.

---

## Contribution Guidelines

Before proposing changes, read [`Agents.md`](Agents.md) — the project's engineering constitution.
The non-negotiables:

1. **Never execute LLM-generated Python.** The model emits JSON; our code owns execution.
2. **Never bypass the validator.** Every action passes through `validator.py` before `action_engine.py`.
3. **Never hard-code anatomy.** No `if "liver" in target`. Use `resolve_target()`.
4. **Never modify the 3D Slicer installation.** This project is loaded as an external module.
5. **Never commit API keys.** Use environment variables or the in-app settings panel.
6. **Always add tests** for new action types and behaviours.
7. **Keep the action set small, explicit, and testable.**

### Adding a new action

A new action touches seven places. The duplication is deliberate — no single edit should be able to
grant the model new power by accident.

| # | File | Change |
| - | ---- | ------ |
| 1 | `schemas.py` | Define the action class with a `Literal` discriminator and typed fields |
| 2 | `schemas.py` | Add to `ALLOWED_ACTIONS` and `ACTION_CLASSES` |
| 3 | `validator.py` | Add target and parameter checks |
| 4 | `action_engine.py` | Add the dispatch branch and `_execute_*` method |
| 5 | `verification.py` | Add `_verify_*` and dispatch to it |
| 6 | `prompts/*.txt`, `knowledge/slicer_actions.json` | Document it so the model can emit it |
| 7 | `tests/` | Add coverage for the new path |

> If you add a file-I/O action, first constrain its `path` parameter. See
> [REVERSE_ENGINEERING.md §10.7](docs/REVERSE_ENGINEERING.md#7-promptschema-coverage-gap) — the
> model-supplied path is not currently validated.

---

## Quick Start for Contributors

```bash
git clone https://github.com/Juhamim/Autoslicer.git
cd Autoslicer
git checkout -b feature/my-change

pip install -r requirements.txt
python -m pytest tests/ -v        # must stay green — 101 passing

# make your change, then
git add -A
git commit -m "Add your feature"
git push origin feature/my-change
```

Then open a pull request.

---

## Contributor Graph

<a href="https://github.com/Juhamim/Autoslicer/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Juhamim/Autoslicer" alt="Contributors" />
</a>

---

## License

Contributions are accepted under the [MIT License](LICENSE). By submitting a pull request you
confirm that you have the right to license your work under it.