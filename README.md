from pathlib import Path

src = Path("/mnt/data/README_attractive.md")
if not src.exists():
    raise FileNotFoundError("The previous README file is not available in this session.")
text = src.read_text(encoding="utf-8")

# Improve the hero layout and add creator identity, profile links, and a polished author section.
text = text.replace(
'''<div align="center">

# 🧠 Slicer AI Copilot

### Natural-language control for 3D Slicer — with validation, trusted execution, and verification.

Turn plain-English instructions into controlled actions on your live medical-imaging scene.  
The AI plans. Your code validates. Slicer executes. The verifier checks what actually changed.

<br/>

[![Platform](https://img.shields.io/badge/Platform-3D%20Slicer-005b87?style=for-the-badge&logo=3d-slicer&logoColor=white)](https://www.slicer.org/)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-101%20passing-2ea44f?style=for-the-badge&logo=pytest&logoColor=white)](tests/)
[![License](https://img.shields.io/badge/License-MIT-7f3fbf?style=for-the-badge)](LICENSE)

**[Quick Start](#-quick-start)** · **[Features](#-features)** · **[Architecture](#-architecture)** · **[Safety](#-safety-first)** · **[Roadmap](#-roadmap)**

</div>''',
'''<div align="center">

# 🧠 SLICER AI COPILOT

### INTELLIGENT · SCENE-AWARE · VERIFIED

**Natural-language control for 3D Slicer**

Turn plain-English instructions into controlled actions on a live medical-imaging scene.

<br/>

[![Platform](https://img.shields.io/badge/PLATFORM-3D%20SLICER-171717?style=for-the-badge&logo=3d-slicer&logoColor=white)](https://www.slicer.org/)
[![Python](https://img.shields.io/badge/PYTHON-3.9%2B-333333?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/TESTS-101%20PASSING-444444?style=for-the-badge&logo=pytest&logoColor=white)](tests/)
[![License](https://img.shields.io/badge/LICENSE-MIT-555555?style=for-the-badge)](LICENSE)

**[Overview](#-the-idea)** &nbsp;•&nbsp; **[Features](#-features-at-a-glance)** &nbsp;•&nbsp; **[Quick Start](#-quick-start)** &nbsp;•&nbsp; **[Architecture](#-architecture)** &nbsp;•&nbsp; **[Safety](#-safety-first)**

<br/>

<sub>DESIGNED AND BUILT BY <a href="https://github.com/Juhamim"><strong>JUHAIM MOHAMMED MT</strong></a></sub>

</div>'''
)

# Add a compact project snapshot after the opening divider.
needle = "---\\n\\n## ✨ The idea"
replacement = '''---

## ◈ Project snapshot

| | |
|---|---|
| **Project** | Slicer AI Copilot |
| **Category** | AI-assisted medical-imaging visualization |
| **Host application** | 3D Slicer |
| **Core approach** | Natural language → structured plan → validation → trusted execution → verification |
| **Primary language** | Python |
| **Maintainer / Creator** | [Juhaim Mohammed MT](https://github.com/Juhamim) |
| **Repository** | [github.com/Juhamim/Autoslicer](https://github.com/Juhamim/Autoslicer) |

> **Core principle:** The model can propose an action, but it does not get unrestricted control over the application.

---

## ✨ The idea'''
text = text.replace(needle, replacement)

# Insert a visual quick workflow section before the architecture.
needle = "---\\n\\n## 🏗️ Architecture"
replacement = '''---

## 🔄 One request, five controlled stages

<table>
<tr>
<td align="center" width="20%"><strong>01 · UNDERSTAND</strong><br/><sub>Read the user's request and live scene context</sub></td>
<td align="center" width="20%"><strong>02 · PLAN</strong><br/><sub>Generate a structured JSON action plan</sub></td>
<td align="center" width="20%"><strong>03 · VALIDATE</strong><br/><sub>Check action types, values, and targets</sub></td>
<td align="center" width="20%"><strong>04 · EXECUTE</strong><br/><sub>Run trusted, allowlisted operations</sub></td>
<td align="center" width="20%"><strong>05 · VERIFY</strong><br/><sub>Re-read scene state and report outcomes</sub></td>
</tr>
</table>

---

## 🏗️ Architecture'''
text = text.replace(needle, replacement)

# Add an author/maintainer section before the medical disclaimer.
needle = "---\\n\\n## ⚕️ Medical disclaimer"
replacement = '''---

## 👨‍💻 About the creator

<div align="center">

### **Juhaim Mohammed MT**

**Engineering Student · Cybersecurity · AI Systems · Full-Stack Development**

I’m an engineering student interested in building practical intelligent systems that combine AI, automation, and secure software engineering. Slicer AI Copilot explores how natural-language interfaces can make complex technical workflows easier to operate while keeping execution constrained, testable, and verifiable.

<br/>

[![GitHub](https://img.shields.io/badge/GitHub-Juhamim-181717?style=for-the-badge&logo=github)](https://github.com/Juhamim)
[![Project Repository](https://img.shields.io/badge/Project-Autoslicer-444444?style=for-the-badge&logo=github)](https://github.com/Juhamim/Autoslicer)
[![ThreatHunter AI](https://img.shields.io/badge/Related_Project-ThreatHunter_AI-333333?style=for-the-badge&logo=github)](https://github.com/Juhamim/threathunder-production)

</div>

**Areas I work on**
- AI-powered applications and agentic workflows
- Cybersecurity automation and defensive tooling
- Full-stack product development
- Reliable systems with validation, least privilege, and clear failure handling

> Want to collaborate, suggest an improvement, or report an issue? Open a [GitHub issue](https://github.com/Juhamim/Autoslicer/issues) or start a discussion through the repository.

---

## ⚕️ Medical disclaimer'''
text = text.replace(needle, replacement)

# Upgrade the footer to tie the project to the creator and keep the layout tidy.
text = text.replace(
'''### 🧠 Slicer AI Copilot

**Understand the scene. Validate the plan. Verify the result.**

Built for hackathon challenge **N35 — Verified natural-language automation of 3D Slicer**.

[⭐ Explore the repository](https://github.com/Juhamim/Autoslicer) · [🐛 Report an issue](https://github.com/Juhamim/Autoslicer/issues)''',
'''### 🧠 SLICER AI COPILOT

**Understand the scene. Validate the plan. Verify the result.**

Built for hackathon challenge **N35 — Verified natural-language automation of 3D Slicer**.

**Created by [Juhaim Mohammed MT](https://github.com/Juhamim)**

[⭐ Explore the repository](https://github.com/Juhamim/Autoslicer) · [🐛 Report an issue](https://github.com/Juhamim/Autoslicer/issues)'''
)

out = Path("/mnt/data/README_Juhaim_Enhanced.md")
out.write_text(text, encoding="utf-8")
print(f"Created: {out}\nCharacters: {len(text):,}\nLines: {len(text.splitlines()):,}")
