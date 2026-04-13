---
name: Use venv for Python packages
description: Never install Python packages globally; always create a venv first
type: feedback
---

Always use a virtual environment for Python dependencies. Never run `pip install` without first creating and activating a venv.

**Why:** User preference — do not pollute the global Python environment.

**How to apply:** Before any `pip install`, create a venv (`python3 -m venv .venv`) if one doesn't exist, then activate it (`source .venv/bin/activate`) before installing packages or running scripts.
