#!/usr/bin/env python3
"""
Scans predictions for upcoming deadlines and posts reminders to Bluesky.
Fires at 30, 7, and 1 days before deadline for status: pending predictions.

Usage:
  python scripts/reminders.py           — live run
  python scripts/reminders.py --dry-run — print what would be posted, no API calls

Required environment variables (for live run):
  BLUESKY_HANDLE
  BLUESKY_APP_PASSWORD
"""

import os
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed.", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).parent.parent
PREDICTIONS_DIR = REPO_ROOT / "predictions"
STATE_FILE = REPO_ROOT / "state" / "reminded.yaml"

REMINDER_THRESHOLDS = [30, 7, 1]  # days before deadline
BLUESKY_CHAR_LIMIT = 300


# ── State management ──────────────────────────────────────────────────────────

def load_state():
    if not STATE_FILE.exists():
        return {"reminders": {}}
    with open(STATE_FILE) as f:
        data = yaml.safe_load(f) or {}
    if "reminders" not in data:
        data["reminders"] = {}
    return data


def save_state(state):
    STATE_FILE.parent.mkdir(exist_ok=True)
    with open(STATE_FILE, "w") as f:
        yaml.dump(state, f, default_flow_style=False, allow_unicode=True)


def already_reminded(state, filename, threshold):
    return threshold in state["reminders"].get(filename, [])


def mark_reminded(state, filename, threshold):
    if filename not in state["reminders"]:
        state["reminders"][filename] = []
    if threshold not in state["reminders"][filename]:
        state["reminders"][filename].append(threshold)


# ── Prediction loading ────────────────────────────────────────────────────────

def load_predictions():
    predictions = []
    for path in sorted(PREDICTIONS_DIR.glob("*.yaml")):
        if path.name == ".gitkeep":
            continue
        with open(path) as f:
            data = yaml.safe_load(f)
        if data:
            data["_filename"] = path.name
            predictions.append(data)
    return predictions


def parse_deadline(value):
    """Returns a date object or None."""
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


# ── Post formatting ───────────────────────────────────────────────────────────

def truncate_to_fit(text, max_chars, ellipsis="…"):
    text = text.strip()
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars - len(ellipsis)].rsplit(" ", 1)[0]
    return truncated + ellipsis


def build_reminder_post(prediction, days_remaining):
    source = str(prediction.get("source_name") or "Unknown").strip()
    text = str(prediction.get("prediction_text") or "").strip()

    if days_remaining == 1:
        countdown = "Tomorrow"
    else:
        countdown = f"{days_remaining} days"

    deadline_fuzzy = str(prediction.get("deadline_fuzzy") or "").strip()
    deadline_iso = str(prediction.get("deadline") or "").strip()
    if deadline_fuzzy:
        deadline_label = deadline_fuzzy
    elif deadline_iso:
        try:
            deadline_label = date.fromisoformat(deadline_iso).strftime("%b %-d, %Y")
        except ValueError:
            deadline_label = deadline_iso
    else:
        deadline_label = "the deadline"

    header = f"{countdown} until {source}'s prediction deadline ({deadline_label}):"
    fixed_chars = len(header) + 2 + 1 + 1  # \n\n + " + "
    available = BLUESKY_CHAR_LIMIT - fixed_chars

    excerpt = truncate_to_fit(text, max(available, 20))
    post = f'{header}\n\n"{excerpt}"'

    if len(post) > BLUESKY_CHAR_LIMIT:
        post = post[:BLUESKY_CHAR_LIMIT - 1] + "…"

    return post


# ── Bluesky posting ───────────────────────────────────────────────────────────

def post_to_bluesky(text, handle, app_password):
    try:
        from atproto import Client
    except ImportError:
        print("ERROR: atproto not installed.", file=sys.stderr)
        sys.exit(2)
    client = Client()
    client.login(handle, app_password)
    client.send_post(text=text)


# ── Main logic ────────────────────────────────────────────────────────────────

def run(today=None, dry_run=False):
    if today is None:
        today = date.today()

    predictions = load_predictions()
    state = load_state()
    handle = os.environ.get("BLUESKY_HANDLE")
    app_password = os.environ.get("BLUESKY_APP_PASSWORD")

    posted_count = 0
    skipped_count = 0

    for prediction in predictions:
        filename = prediction["_filename"]

        # Skip ineligible predictions
        if prediction.get("status") != "pending":
            continue
        if prediction.get("skip_post"):
            continue

        deadline = parse_deadline(prediction.get("deadline"))
        if deadline is None:
            continue

        days_remaining = (deadline - today).days

        for threshold in REMINDER_THRESHOLDS:
            if days_remaining != threshold:
                continue
            if already_reminded(state, filename, threshold):
                skipped_count += 1
                print(f"  Already sent {threshold}d reminder for {filename}")
                continue

            post = build_reminder_post(prediction, days_remaining)
            print(f"\n[{threshold}d reminder] {filename}")
            print("─" * 40)
            print(post)
            print(f"[{len(post)} chars]")

            if dry_run:
                print("(dry run — not posted)")
            else:
                if not handle or not app_password:
                    print("ERROR: BLUESKY_HANDLE and BLUESKY_APP_PASSWORD must be set.", file=sys.stderr)
                    sys.exit(1)
                post_to_bluesky(post, handle, app_password)
                mark_reminded(state, filename, threshold)
                print("Posted.")
            posted_count += 1

    if not dry_run:
        save_state(state)

    print(f"\nDone. {posted_count} reminder(s) posted, {skipped_count} already sent.")
    return posted_count


def main():
    dry_run = "--dry-run" in sys.argv
    run(dry_run=dry_run)


if __name__ == "__main__":
    main()
