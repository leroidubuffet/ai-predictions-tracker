#!/usr/bin/env python3
"""
Posts a new prediction to Bluesky.
Usage: post_new.py <path/to/prediction.yaml>

Skips files where skip_post: true.
Exits 0 on success or skip, non-zero on failure.

Required environment variables:
  BLUESKY_HANDLE       — bot account handle (e.g. aipredictions.bsky.social)
  BLUESKY_APP_PASSWORD — Bluesky app password
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

BLUESKY_CHAR_LIMIT = 300


def load_prediction(path):
    with open(path) as f:
        return yaml.safe_load(f)


def format_date(value):
    if not value:
        return ""
    if isinstance(value, (date, datetime)):
        return str(value.year)
    try:
        return str(date.fromisoformat(str(value)).year)
    except ValueError:
        return str(value)


def deadline_display(prediction):
    fuzzy = str(prediction.get("deadline_fuzzy") or "").strip()
    if fuzzy:
        return fuzzy
    iso = str(prediction.get("deadline") or "").strip()
    if iso:
        try:
            d = date.fromisoformat(iso)
            return d.strftime("%b %-d, %Y")
        except ValueError:
            return iso
    return ""


def truncate_to_fit(text, max_chars, ellipsis="…"):
    """Truncate text to max_chars at a word boundary."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars - len(ellipsis)].rsplit(" ", 1)[0]
    return truncated + ellipsis


def build_post(prediction):
    """
    Build the Bluesky post text for a prediction.
    Returns the post string (≤ 300 chars).

    Format:
      [Source] ([year]):
      "[excerpt]"

      Deadline: [deadline]
    """
    source = str(prediction.get("source_name") or "Unknown").strip()
    year = format_date(prediction.get("prediction_date"))
    text = str(prediction.get("prediction_text") or "").strip()
    deadline = deadline_display(prediction)

    # Build the fixed parts to measure available space for the excerpt
    header = f"{source} ({year}):"
    deadline_line = f"\n\nDeadline: {deadline}" if deadline else ""

    # Account for header + newline + opening quote + closing quote + deadline
    # Pattern: "{header}\n\"{excerpt}\"{deadline_line}"
    fixed_chars = len(header) + 1 + 1 + 1 + len(deadline_line)  # \n + " + "
    available = BLUESKY_CHAR_LIMIT - fixed_chars

    excerpt = truncate_to_fit(text, max(available, 20))

    post = f'{header}\n"{excerpt}"{deadline_line}'

    # Final safety clamp (should not be needed, but guards against edge cases)
    if len(post) > BLUESKY_CHAR_LIMIT:
        post = post[:BLUESKY_CHAR_LIMIT - 1] + "…"

    return post


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
            # Rate limited or transient server error — retry with backoff
            if attempt < retries and ("RateLimitExceeded" in str(e) or "502" in str(e) or "503" in str(e)):
                wait = backoff * attempt
                print(f"  API error on attempt {attempt}/{retries}: {e}. Retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <prediction.yaml>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(1)

    prediction = load_prediction(path)

    if prediction.get("skip_post"):
        print(f"Skipping {path.name} (skip_post: true)")
        sys.exit(0)

    post = build_post(prediction)
    print("Post preview:")
    print("─" * 40)
    print(post)
    print("─" * 40)
    print(f"Length: {len(post)}/300 chars")

    handle = os.environ.get("BLUESKY_HANDLE")
    app_password = os.environ.get("BLUESKY_APP_PASSWORD")

    if not handle or not app_password:
        print("ERROR: BLUESKY_HANDLE and BLUESKY_APP_PASSWORD must be set.", file=sys.stderr)
        sys.exit(1)

    post_to_bluesky(post, handle, app_password)
    print(f"Posted: {path.name}")


if __name__ == "__main__":
    main()
