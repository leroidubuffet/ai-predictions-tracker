#!/usr/bin/env python3
"""
Checks for drift between state/reminded.yaml and predictions/.
Reports entries in state that have no corresponding prediction file.
Exits non-zero if drift is found.

Usage: python scripts/check_state.py
"""

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed.", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).parent.parent
PREDICTIONS_DIR = REPO_ROOT / "predictions"
STATE_FILE = REPO_ROOT / "state" / "reminded.yaml"


def main():
    if not STATE_FILE.exists():
        print("state/reminded.yaml not found — nothing to check.")
        sys.exit(0)

    with open(STATE_FILE) as f:
        state = yaml.safe_load(f) or {}

    reminders = state.get("reminders", {})
    if not reminders:
        print("No reminder state recorded yet.")
        sys.exit(0)

    existing_files = {p.name for p in PREDICTIONS_DIR.glob("*.yaml")}
    orphaned = [name for name in reminders if name not in existing_files]

    if orphaned:
        print(f"DRIFT DETECTED: {len(orphaned)} state entry(ies) have no matching prediction file:")
        for name in sorted(orphaned):
            print(f"  {name}")
        print("\nTo fix: remove these entries from state/reminded.yaml manually.")
        sys.exit(1)
    else:
        print(f"OK — {len(reminders)} state entry(ies), all have matching prediction files.")


if __name__ == "__main__":
    main()
