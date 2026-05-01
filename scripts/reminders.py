#!/usr/bin/env python3
"""
Scans predictions for upcoming deadlines and posts reminders to Bluesky.

Reminder thresholds are tiered by prediction horizon:
  Multi-year:  annual milestones (e.g. 365, 730 days out) + 30, 7, 1 days
  < 1 year:    30, 7, 1 days

Predictions whose deadline has already passed receive a single "expired" post.
Predictions made ≥ 1 year ago are introduced with an age label ("2 years ago,
they predicted:") to give readers context.

Usage:
  python scripts/reminders.py           — live run
  python scripts/reminders.py --dry-run — print what would be posted, no API calls

Required environment variables (for live run):
  BLUESKY_HANDLE
  BLUESKY_APP_PASSWORD
"""

import os
import sys
import time
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
CATEGORIES_FILE = REPO_ROOT / "categories.yaml"

BLUESKY_CHAR_LIMIT = 300
CAMPAIGN_TAG = "#AIPredictions"
HASHTAGS = CAMPAIGN_TAG  # retained for test compatibility


def _load_category_hashtags():
    try:
        with open(CATEGORIES_FILE) as f:
            data = yaml.safe_load(f)
        return data.get("category_hashtags", {})
    except Exception:
        return {}


_CATEGORY_HASHTAGS = _load_category_hashtags()


def get_hashtags(prediction, category_hashtags=None):
    """Return hashtags for this prediction.

    Priority: per-prediction override → category defaults → campaign tag only.
    The campaign tag is always prepended to category defaults automatically.
    """
    custom = str(prediction.get("hashtags") or "").strip()
    if custom:
        return custom
    if category_hashtags is None:
        category_hashtags = _CATEGORY_HASHTAGS
    category = str(prediction.get("category") or "").strip()
    topic_tags = (category_hashtags.get(category) or "").strip()
    if topic_tags:
        return f"{CAMPAIGN_TAG} {topic_tags}"
    return CAMPAIGN_TAG

# Sentinel stored in state to record that an expired post was sent
EXPIRED_KEY = "expired"


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


# ── Anniversary logic ────────────────────────────────────────────────────────

def get_anniversary_year(prediction_date, today):
    """
    Returns the anniversary year number if today is exactly N years after
    prediction_date (N ≥ 1), otherwise None.
    Feb 29 predictions are celebrated on Feb 28 in non-leap years.
    """
    if not isinstance(prediction_date, date):
        return None
    if today.month == prediction_date.month and today.day == prediction_date.day:
        years = today.year - prediction_date.year
        return years if years >= 1 else None
    # Handle Feb 29 predictions: fire on Feb 28 in non-leap years
    if prediction_date.month == 2 and prediction_date.day == 29:
        if today.month == 2 and today.day == 28:
            import calendar
            if not calendar.isleap(today.year):
                years = today.year - prediction_date.year
                return years if years >= 1 else None
    return None


# ── Threshold logic ───────────────────────────────────────────────────────────

def get_thresholds(horizon_days):
    """
    Return reminder thresholds (days before deadline) based on prediction horizon.
    Multi-year predictions get annual milestones added to the standard close-in set.
    Thresholds are returned in descending order.
    """
    base = [30, 7, 1]
    yearly = []
    full_years = horizon_days // 365
    for y in range(1, full_years + 1):
        t = y * 365
        if t > 30:
            yearly.append(t)
    return sorted(set(base + yearly), reverse=True)


# ── Post formatting ───────────────────────────────────────────────────────────

def get_post_text(prediction):
    """Return post_excerpt if set, else prediction_text."""
    excerpt = str(prediction.get("post_excerpt") or "").strip()
    return excerpt if excerpt else str(prediction.get("prediction_text") or "").strip()


def truncate_to_fit(text, max_chars, ellipsis="…"):
    """Truncate text to max_chars, preferring sentence then word boundaries."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    budget = max_chars - len(ellipsis)
    chunk = text[:budget]
    for punct in (".", "!", "?"):
        idx = chunk.rfind(punct)
        if idx > budget // 3:
            return chunk[:idx + 1] + ellipsis
    return chunk.rsplit(" ", 1)[0] + ellipsis


def prediction_age_label(prediction_date_str, today):
    """
    Returns a human-readable age string if the prediction is ≥ 1 year old.
    Examples: "1 year ago", "2 years ago".
    Returns None for predictions < 1 year old or unparseable dates.
    """
    if not prediction_date_str:
        return None
    try:
        pred_date = date.fromisoformat(str(prediction_date_str))
    except (ValueError, TypeError):
        return None
    days = (today - pred_date).days
    if days < 365:
        return None
    whole_years = days // 365
    remainder_days = days % 365
    if remainder_days >= 335:
        whole_years += 1
    if whole_years == 1:
        return "1 year ago"
    return f"{whole_years} years ago"


def days_label(days_remaining):
    """Returns a human-readable countdown string."""
    if days_remaining == 1:
        return "Tomorrow"
    if days_remaining >= 365 and days_remaining % 365 == 0:
        years = days_remaining // 365
        return f"{years} year{'s' if years != 1 else ''}"
    return f"{days_remaining} days"


def _deadline_label(prediction):
    fuzzy = str(prediction.get("deadline_fuzzy") or "").strip()
    if fuzzy:
        return fuzzy
    iso = str(prediction.get("deadline") or "").strip()
    if iso:
        try:
            return date.fromisoformat(iso).strftime("%b %-d, %Y")
        except ValueError:
            return iso
    return "the deadline"


def build_reminder_post(prediction, days_remaining, today=None):
    """
    Build a countdown reminder post.
    Predictions ≥ 1 year old include an age-framing line before the quote.

    Format (with age):
      {countdown} left on {source}'s prediction ({deadline}):

      {N years ago}, they predicted:
      "{excerpt}"

      #AIPredictions

    Format (without age):
      {countdown} left on {source}'s prediction ({deadline}):

      "{excerpt}"

      #AIPredictions
    """
    if today is None:
        today = date.today()

    source = str(prediction.get("source_name") or "Unknown").strip()
    raw_text = get_post_text(prediction)
    text = " ".join(raw_text.split())

    deadline_lbl = _deadline_label(prediction)
    countdown = days_label(days_remaining)
    age = prediction_age_label(prediction.get("prediction_date"), today)

    if days_remaining == 1:
        header = f"Tomorrow: {source}'s prediction deadline ({deadline_lbl}):"
    else:
        header = f"{countdown} left on {source}'s prediction ({deadline_lbl}):"

    age_line = f"{age.capitalize()}, they predicted:" if age else ""

    hashtags = get_hashtags(prediction)

    # Budget: {header}\n\n[{age_line}\n\n]"{excerpt}"\n\n{hashtags}
    fixed = len(header) + 2 + 2 + 2 + len(hashtags)  # separators + quotes
    if age_line:
        fixed += len(age_line) + 2
    available = BLUESKY_CHAR_LIMIT - fixed

    excerpt = truncate_to_fit(text, max(available, 20))

    parts = [header]
    if age_line:
        parts.append(age_line)
    parts.append(f'"{excerpt}"')
    parts.append(hashtags)

    post = "\n\n".join(parts)

    if len(post) > BLUESKY_CHAR_LIMIT:
        post = post[:BLUESKY_CHAR_LIMIT - 1] + "…"

    return post


def build_anniversary_post(prediction, years):
    """
    Build a yearly anniversary post for any prediction, with or without a deadline.

    Format:
      N year(s) ago, {source} predicted:

      "{excerpt}"

      #AIPredictions
    """
    source = str(prediction.get("source_name") or "Unknown").strip()
    raw_text = get_post_text(prediction)
    text = " ".join(raw_text.split())

    if years == 1:
        header = f"1 year ago, {source} predicted:"
    else:
        header = f"{years} years ago, {source} predicted:"

    hashtags = get_hashtags(prediction)
    fixed = len(header) + 2 + 2 + 2 + len(hashtags)
    available = BLUESKY_CHAR_LIMIT - fixed

    excerpt = truncate_to_fit(text, max(available, 20))
    post = "\n\n".join([header, f'"{excerpt}"', hashtags])

    if len(post) > BLUESKY_CHAR_LIMIT:
        post = post[:BLUESKY_CHAR_LIMIT - 1] + "…"

    return post


def build_expired_post(prediction, today=None):
    """
    Build a one-time post for predictions whose deadline has passed.

    Format:
      {source}'s prediction deadline has passed ({deadline}):

      {N years ago}, they predicted:
      "{excerpt}"

      #AIPredictions
    """
    if today is None:
        today = date.today()

    source = str(prediction.get("source_name") or "Unknown").strip()
    raw_text = get_post_text(prediction)
    text = " ".join(raw_text.split())

    deadline_lbl = _deadline_label(prediction)
    age = prediction_age_label(prediction.get("prediction_date"), today)

    header = f"{source}'s prediction deadline has passed ({deadline_lbl}):"
    age_line = f"{age.capitalize()}, they predicted:" if age else ""

    hashtags = get_hashtags(prediction)
    fixed = len(header) + 2 + 2 + 2 + len(hashtags)
    if age_line:
        fixed += len(age_line) + 2
    available = BLUESKY_CHAR_LIMIT - fixed

    excerpt = truncate_to_fit(text, max(available, 20))

    parts = [header]
    if age_line:
        parts.append(age_line)
    parts.append(f'"{excerpt}"')
    parts.append(hashtags)

    post = "\n\n".join(parts)

    if len(post) > BLUESKY_CHAR_LIMIT:
        post = post[:BLUESKY_CHAR_LIMIT - 1] + "…"

    return post


# ── Elapsed-time reminders (no-deadline predictions) ─────────────────────────

def get_elapsed_interval(importance):
    """Return the reminder interval in days for no-deadline predictions."""
    return 183 if importance == "high" else 365


def elapsed_label(days):
    """Return a human-readable elapsed-time label: '6 months', '1 year', '18 months', etc."""
    months = round(days / 30.44)
    if months % 12 == 0:
        years = months // 12
        return f"{years} year{'s' if years != 1 else ''}"
    return f"{months} months"


def build_elapsed_post(prediction, age_label):
    """
    Build a periodic reminder post for a prediction with no deadline.

    Format:
      {age_label} ago, {source} predicted:

      "{excerpt}"

      #AIPredictions
    """
    source = str(prediction.get("source_name") or "Unknown").strip()
    raw_text = get_post_text(prediction)
    text = " ".join(raw_text.split())
    header = f"{age_label} ago, {source} predicted:"
    hashtags = get_hashtags(prediction)
    fixed = len(header) + 2 + 2 + 2 + len(hashtags)
    available = BLUESKY_CHAR_LIMIT - fixed
    excerpt = truncate_to_fit(text, max(available, 20))
    post = "\n\n".join([header, f'"{excerpt}"', hashtags])
    if len(post) > BLUESKY_CHAR_LIMIT:
        post = post[:BLUESKY_CHAR_LIMIT - 1] + "…"
    return post


# ── Bluesky posting ───────────────────────────────────────────────────────────

def post_to_bluesky(text, handle, app_password, retries=3, backoff=5):
    try:
        from atproto import Client
        from atproto_client.exceptions import AtProtocolError
    except ImportError:
        print("ERROR: atproto not installed.", file=sys.stderr)
        sys.exit(2)

    client = Client()
    client.login(handle, app_password)

    for attempt in range(1, retries + 1):
        try:
            client.send_post(text=text)
            return
        except AtProtocolError as e:
            if attempt < retries and ("RateLimitExceeded" in str(e) or "502" in str(e) or "503" in str(e)):
                wait = backoff * attempt
                print(f"  API error on attempt {attempt}/{retries}: {e}. Retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise


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

        if prediction.get("status") != "pending":
            continue
        if prediction.get("skip_post"):
            continue

        prediction_date = parse_deadline(prediction.get("prediction_date"))
        deadline = parse_deadline(prediction.get("deadline"))

        # ── No-deadline predictions: elapsed-time reminders ───────────────────
        if deadline is None:
            if prediction_date:
                days_elapsed = (today - prediction_date).days
                importance = str(prediction.get("importance") or "low").strip()
                interval = get_elapsed_interval(importance)
                threshold = interval
                while threshold <= days_elapsed:
                    key = f"elapsed_{threshold}"
                    if not already_reminded(state, filename, key):
                        label = elapsed_label(threshold)
                        post = build_elapsed_post(prediction, label)
                        print(f"\n[{label} elapsed] {filename}")
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
                            mark_reminded(state, filename, key)
                            print("Posted.")
                        posted_count += 1
                    else:
                        skipped_count += 1
                    threshold += interval
            continue

        # ── Anniversary post (fires for predictions with a deadline) ──────────
        years = get_anniversary_year(prediction_date, today) if prediction_date else None
        if years:
            key = f"anniversary_{years}"
            if not already_reminded(state, filename, key):
                post = build_anniversary_post(prediction, years)
                print(f"\n[{years}y anniversary] {filename}")
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
                    mark_reminded(state, filename, key)
                    print("Posted.")
                posted_count += 1
            else:
                skipped_count += 1

        days_remaining = (deadline - today).days

        # ── Expired prediction ────────────────────────────────────────────────
        if days_remaining < 0:
            if already_reminded(state, filename, EXPIRED_KEY):
                skipped_count += 1
                continue
            post = build_expired_post(prediction, today)
            print(f"\n[expired] {filename}")
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
                mark_reminded(state, filename, EXPIRED_KEY)
                print("Posted.")
            posted_count += 1
            continue

        # ── Upcoming deadline reminders ───────────────────────────────────────
        horizon_days = (deadline - prediction_date).days if prediction_date else days_remaining
        thresholds = get_thresholds(horizon_days)

        for threshold in thresholds:
            if days_remaining != threshold:
                continue
            if already_reminded(state, filename, threshold):
                skipped_count += 1
                print(f"  Already sent {days_label(threshold)} reminder for {filename}")
                continue

            post = build_reminder_post(prediction, days_remaining, today)
            print(f"\n[{days_label(threshold)} reminder] {filename}")
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
