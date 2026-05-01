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
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CATEGORIES_FILE = REPO_ROOT / "categories.yaml"
POSTED_FILE = REPO_ROOT / "state" / "posted.yaml"


def _load_category_hashtags():
    try:
        with open(CATEGORIES_FILE) as f:
            data = yaml.safe_load(f)
        return data.get("category_hashtags", {})
    except Exception:
        return {}


_CATEGORY_HASHTAGS = _load_category_hashtags()

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed.", file=sys.stderr)
    sys.exit(2)

BLUESKY_CHAR_LIMIT = 300


def load_posted():
    if not POSTED_FILE.exists():
        return {"posts": {}}
    with open(POSTED_FILE) as f:
        data = yaml.safe_load(f) or {}
    if "posts" not in data:
        data["posts"] = {}
    return data


def record_post(filename):
    data = load_posted()
    data["posts"][filename] = {"posted_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
    POSTED_FILE.parent.mkdir(exist_ok=True)
    with open(POSTED_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def load_prediction(path):
    with open(path) as f:
        return yaml.safe_load(f)


def format_date(value):
    """Return 'Month YYYY' string from an ISO date or date object."""
    if not value:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%B %Y")
    try:
        return date.fromisoformat(str(value)).strftime("%B %Y")
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


CAMPAIGN_TAG = "#AIPredictions"
HASHTAGS = CAMPAIGN_TAG  # retained for test compatibility


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


def build_post(prediction):
    """
    Build the Bluesky post text for a new prediction.
    The source URL is NOT included in the text — it is attached as an embed
    card by post_to_bluesky(), so it costs zero characters here.
    Returns the post string (≤ 300 chars).

    Format:
      New prediction registered

      Author: [source_name]
      Date: [Month YYYY]

      "[full excerpt — no internal line breaks]"

      Deadline: [deadline]     ← omitted if absent

      #AIPredictions
    """
    source = str(prediction.get("source_name") or "Unknown").strip()
    date_str = format_date(prediction.get("prediction_date"))
    # Collapse internal line breaks in the prediction text to spaces
    raw_text = str(prediction.get("prediction_text") or "").strip()
    text = " ".join(raw_text.split())
    deadline = deadline_display(prediction)

    header = "🔮 New prediction registered 🔮"
    byline = f"By: {source}\nDate: {date_str}"
    hashtags = get_hashtags(prediction)
    deadline_line = f"Deadline: {deadline}" if deadline else ""
    footer_parts = [p for p in [deadline_line, hashtags] if p]
    footer = "\n\n".join(footer_parts)

    # Measure fixed chars to calculate available space for the quote
    # Pattern: "{header}\n\n{byline}\n\n\"{excerpt}\"\n\n{footer}"
    fixed = len(header) + 2 + len(byline) + 2 + 2 + 2 + len(footer)  # quotes + separators
    available = BLUESKY_CHAR_LIMIT - fixed

    excerpt = truncate_to_fit(text, max(available, 20))

    parts = [header, byline, f'"{excerpt}"']
    if footer:
        parts.append(footer)

    post = "\n\n".join(parts)

    # Safety clamp
    if len(post) > BLUESKY_CHAR_LIMIT:
        post = post[:BLUESKY_CHAR_LIMIT - 1] + "…"

    return post


URL_RE = re.compile(r"https?://[^\s]+")
HASHTAG_RE = re.compile(r"#(\w+)")


def build_facets(text):
    """
    Scan post text and return a list of AT Protocol rich-text facets for
    URLs (app.bsky.richtext.facet#link) and hashtags (facet#tag).
    Byte offsets are computed from the UTF-8 encoding of the text.
    """
    try:
        from atproto import models
    except ImportError:
        return []

    text_bytes = text.encode("utf-8")
    facets = []

    for m in URL_RE.finditer(text):
        byte_start = len(text[: m.start()].encode("utf-8"))
        byte_end = len(text[: m.end()].encode("utf-8"))
        facets.append(
            models.AppBskyRichtextFacet.Main(
                index=models.AppBskyRichtextFacet.ByteSlice(
                    byte_start=byte_start,
                    byte_end=byte_end,
                ),
                features=[models.AppBskyRichtextFacet.Link(uri=m.group())],
            )
        )

    for m in HASHTAG_RE.finditer(text):
        byte_start = len(text[: m.start()].encode("utf-8"))
        byte_end = len(text[: m.end()].encode("utf-8"))
        facets.append(
            models.AppBskyRichtextFacet.Main(
                index=models.AppBskyRichtextFacet.ByteSlice(
                    byte_start=byte_start,
                    byte_end=byte_end,
                ),
                features=[models.AppBskyRichtextFacet.Tag(tag=m.group(1))],
            )
        )

    return facets


def build_embed(url):
    """Return an external embed card for the given URL, or None if url is empty."""
    if not url:
        return None
    try:
        from atproto import models
        return models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                uri=url,
                title="",
                description="",
            )
        )
    except ImportError:
        return None


def upload_screenshot(client, path):
    """Upload an image file and return an AppBskyEmbedImages embed, or None on failure."""
    try:
        from atproto import models
        with open(path, "rb") as f:
            data = f.read()
        response = client.upload_blob(data)
        return models.AppBskyEmbedImages.Main(
            images=[
                models.AppBskyEmbedImages.Image(
                    image=response.blob,
                    alt="Screenshot of original source",
                )
            ]
        )
    except Exception as e:
        print(f"WARNING: Could not upload screenshot: {e}", file=sys.stderr)
        return None


def post_to_bluesky(text, handle, app_password, url="", screenshot_path=None, retries=3, backoff=5):
    try:
        from atproto import Client
        from atproto_client.exceptions import AtProtocolError
    except ImportError:
        print("ERROR: atproto not installed.", file=sys.stderr)
        sys.exit(2)

    client = Client()
    client.login(handle, app_password)
    facets = build_facets(text)
    if screenshot_path:
        embed = upload_screenshot(client, screenshot_path) or build_embed(url)
    else:
        embed = build_embed(url)

    for attempt in range(1, retries + 1):
        try:
            client.send_post(
                text=text,
                facets=facets if facets else None,
                embed=embed,
            )
            return
        except AtProtocolError as e:
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

    url = str(prediction.get("source_url") or "").strip()
    screenshot = str(prediction.get("screenshot") or "").strip()
    screenshot_path = (REPO_ROOT / screenshot) if screenshot else None
    post_to_bluesky(post, handle, app_password, url=url, screenshot_path=screenshot_path)
    record_post(path.name)
    print(f"Posted: {path.name}")


if __name__ == "__main__":
    main()
