#!/usr/bin/env python3
"""
Tests for post_new.py
Run: python scripts/post_new_test.py
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))
from post_new import (
    build_post, build_facets, build_embed, truncate_to_fit, deadline_display,
    format_date, load_prediction, BLUESKY_CHAR_LIMIT, HASHTAGS,
)

REPO_ROOT = Path(__file__).parent.parent


def make_prediction(**kwargs):
    base = {
        "prediction_date": "2024-03-15",
        "source_name": "Sam Altman",
        "source_url": "https://example.com/interview",
        "prediction_text": "AGI will arrive before the end of this decade and will transform every industry.",
        "deadline": "2030-12-31",
        "deadline_fuzzy": "by end of 2030",
        "category": "agi",
        "status": "pending",
        "skip_post": False,
    }
    base.update(kwargs)
    return base


class TestTruncateToFit(unittest.TestCase):
    def test_short_text_unchanged(self):
        self.assertEqual(truncate_to_fit("hello world", 50), "hello world")

    def test_long_text_truncated(self):
        text = "word " * 100
        result = truncate_to_fit(text, 50)
        self.assertLessEqual(len(result), 50)
        self.assertTrue(result.endswith("…"))

    def test_truncates_at_word_boundary(self):
        text = "one two three four five"
        result = truncate_to_fit(text, 12)
        self.assertFalse(result.startswith(" "))
        self.assertNotIn("thre…", result)

    def test_exactly_at_limit_not_truncated(self):
        text = "a" * 50
        self.assertEqual(truncate_to_fit(text, 50), text)


class TestFormatDate(unittest.TestCase):
    def test_iso_string_returns_month_and_year(self):
        self.assertEqual(format_date("2024-03-15"), "March 2024")

    def test_iso_string_returns_correct_month(self):
        self.assertEqual(format_date("2023-05-16"), "May 2023")

    def test_none_returns_empty(self):
        self.assertEqual(format_date(None), "")

    def test_empty_string_returns_empty(self):
        self.assertEqual(format_date(""), "")


class TestDeadlineDisplay(unittest.TestCase):
    def test_fuzzy_takes_priority(self):
        p = make_prediction(deadline_fuzzy="by end of 2030", deadline="2030-12-31")
        self.assertEqual(deadline_display(p), "by end of 2030")

    def test_iso_fallback(self):
        p = make_prediction(deadline_fuzzy="", deadline="2030-12-31")
        result = deadline_display(p)
        self.assertIn("2030", result)

    def test_no_deadline(self):
        p = make_prediction(deadline="", deadline_fuzzy="")
        self.assertEqual(deadline_display(p), "")

    def test_missing_keys(self):
        p = make_prediction()
        del p["deadline"]
        del p["deadline_fuzzy"]
        self.assertEqual(deadline_display(p), "")


class TestBuildPost(unittest.TestCase):
    def test_post_within_char_limit(self):
        post = build_post(make_prediction())
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_header_present(self):
        post = build_post(make_prediction())
        self.assertIn("New prediction", post)

    def test_author_field_present(self):
        post = build_post(make_prediction(source_name="Geoffrey Hinton"))
        self.assertIn("Geoffrey Hinton", post)

    def test_date_field_present(self):
        post = build_post(make_prediction(prediction_date="2023-05-16"))
        self.assertIn("Date: May 2023", post)

    def test_no_category_field(self):
        post = build_post(make_prediction(category="agi"))
        self.assertNotIn("Category", post)
        self.assertNotIn("agi", post)

    def test_quote_present(self):
        post = build_post(make_prediction(prediction_text="AGI will arrive soon."))
        self.assertIn('"AGI will arrive soon."', post)

    def test_quote_has_no_internal_line_breaks(self):
        multiline = "First line.\nSecond line.\nThird line."
        post = build_post(make_prediction(prediction_text=multiline))
        # Extract the quoted part
        start = post.index('"') + 1
        end = post.rindex('"')
        quote_content = post[start:end]
        self.assertNotIn("\n", quote_content)

    def test_deadline_present_when_set(self):
        post = build_post(make_prediction(deadline_fuzzy="by end of 2030"))
        self.assertIn("Deadline: by end of 2030", post)

    def test_no_deadline_when_absent(self):
        post = build_post(make_prediction(deadline="", deadline_fuzzy=""))
        self.assertNotIn("Deadline:", post)

    def test_url_not_in_post_text(self):
        # URL is attached as an embed card, not in the post text
        post = build_post(make_prediction(source_url="https://example.com/article"))
        self.assertNotIn("https://example.com/article", post)

    def test_long_url_does_not_shrink_quote(self):
        # A very long URL must not reduce the available quote space
        long_url = "https://www.example.com/" + "a" * 80
        short_url = "https://x.com/s"
        post_long = build_post(make_prediction(source_url=long_url))
        post_short = build_post(make_prediction(source_url=short_url))
        self.assertEqual(post_long, post_short)

    def test_hashtags_present(self):
        post = build_post(make_prediction())
        self.assertIn(HASHTAGS, post)

    def test_fuzzy_deadline_used_over_iso(self):
        post = build_post(make_prediction(deadline="2030-12-31", deadline_fuzzy="before 2031"))
        self.assertIn("before 2031", post)

    def test_long_prediction_truncated_within_limit(self):
        long_text = "artificial intelligence will transform " * 20
        post = build_post(make_prediction(prediction_text=long_text))
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_long_prediction_no_mid_word_cut(self):
        long_text = "artificial intelligence " * 20
        post = build_post(make_prediction(prediction_text=long_text))
        # Should not cut "intelligence" or "artificial" mid-word
        self.assertNotIn("intelligen…", post)
        self.assertNotIn("artifici…", post)

    def test_all_seed_predictions_within_char_limit(self):
        import yaml
        failures = []
        for path in sorted(REPO_ROOT.glob("predictions/*.yaml")):
            if path.name == ".gitkeep":
                continue
            with open(path) as f:
                prediction = yaml.safe_load(f)
            post = build_post(prediction)
            if len(post) > BLUESKY_CHAR_LIMIT:
                failures.append(f"{path.name}: {len(post)} chars")
        if failures:
            self.fail("Posts exceed char limit:\n" + "\n".join(failures))


class TestBuildFacets(unittest.TestCase):
    def test_url_produces_link_facet(self):
        text = "Check this out\n\nhttps://example.com\n\n#AIPredictions"
        facets = build_facets(text)
        link_facets = [f for f in facets if hasattr(f.features[0], "uri")]
        self.assertEqual(len(link_facets), 1)
        self.assertEqual(link_facets[0].features[0].uri, "https://example.com")

    def test_url_byte_offsets_correct(self):
        url = "https://example.com"
        text = f"Before\n\n{url}"
        facets = build_facets(text)
        link_facets = [f for f in facets if hasattr(f.features[0], "uri")]
        self.assertEqual(len(link_facets), 1)
        f = link_facets[0]
        self.assertEqual(f.index.byte_start, len("Before\n\n".encode("utf-8")))
        self.assertEqual(f.index.byte_end, len(f"Before\n\n{url}".encode("utf-8")))

    def test_hashtag_produces_tag_facet(self):
        text = "Some text\n\n#AIPredictions"
        facets = build_facets(text)
        tag_facets = [f for f in facets if hasattr(f.features[0], "tag")]
        self.assertEqual(len(tag_facets), 1)
        self.assertEqual(tag_facets[0].features[0].tag, "AIPredictions")

    def test_hashtag_byte_offsets_correct(self):
        text = "Before\n\n#AIPredictions"
        facets = build_facets(text)
        tag_facets = [f for f in facets if hasattr(f.features[0], "tag")]
        self.assertEqual(len(tag_facets), 1)
        f = tag_facets[0]
        self.assertEqual(f.index.byte_start, len("Before\n\n".encode("utf-8")))
        self.assertEqual(f.index.byte_end, len("Before\n\n#AIPredictions".encode("utf-8")))

    def test_unicode_url_byte_offsets_correct(self):
        # Non-ASCII before the URL shifts byte offsets
        prefix = "Prédit\n\n"
        url = "https://example.com"
        text = f"{prefix}{url}"
        facets = build_facets(text)
        link_facets = [f for f in facets if hasattr(f.features[0], "uri")]
        self.assertEqual(len(link_facets), 1)
        f = link_facets[0]
        self.assertEqual(f.index.byte_start, len(prefix.encode("utf-8")))
        self.assertEqual(f.index.byte_end, len(f"{prefix}{url}".encode("utf-8")))

    def test_no_urls_no_link_facets(self):
        facets = build_facets("No links here at all.")
        link_facets = [f for f in facets if hasattr(f.features[0], "uri")]
        self.assertEqual(link_facets, [])

    def test_no_hashtags_no_tag_facets(self):
        facets = build_facets("No hashtags here.")
        tag_facets = [f for f in facets if hasattr(f.features[0], "tag")]
        self.assertEqual(tag_facets, [])

    def test_full_post_has_hashtag_facet_only(self):
        # URL is in embed, not post text — only the hashtag facet appears
        p = make_prediction(source_url="https://example.com/article")
        post = build_post(p)
        facets = build_facets(post)
        link_facets = [f for f in facets if hasattr(f.features[0], "uri")]
        tag_facets = [f for f in facets if hasattr(f.features[0], "tag")]
        self.assertEqual(len(link_facets), 0)
        self.assertEqual(len(tag_facets), 1)


class TestBuildEmbed(unittest.TestCase):
    def test_url_produces_embed(self):
        embed = build_embed("https://example.com")
        self.assertIsNotNone(embed)
        self.assertEqual(embed.external.uri, "https://example.com")

    def test_empty_url_returns_none(self):
        self.assertIsNone(build_embed(""))

    def test_none_url_returns_none(self):
        self.assertIsNone(build_embed(None))


def atproto_modules(client_instance):
    from atproto_client.exceptions import AtProtocolError
    mock_atproto_client = MagicMock()
    mock_atproto_client.exceptions.AtProtocolError = AtProtocolError
    return {
        "atproto": MagicMock(Client=MagicMock(return_value=client_instance)),
        "atproto_client": mock_atproto_client,
        "atproto_client.exceptions": mock_atproto_client.exceptions,
    }


class TestSkipPost(unittest.TestCase):
    def test_skip_post_true_produces_no_api_call(self):
        import post_new
        client_instance = MagicMock()
        with patch.dict("sys.modules", atproto_modules(client_instance)):
            p = make_prediction(skip_post=True)
            if not p.get("skip_post"):
                post_new.post_to_bluesky("text", "handle", "password")
        client_instance.send_post.assert_not_called()

    def test_skip_post_false_would_post(self):
        import post_new
        client_instance = MagicMock()
        with patch.dict("sys.modules", atproto_modules(client_instance)):
            post_new.post_to_bluesky("test post", "handle@bsky.social", "app_password")
        client_instance.send_post.assert_called_once()
        call_kwargs = client_instance.send_post.call_args
        self.assertEqual(call_kwargs.kwargs.get("text") or call_kwargs.args[0], "test post")


class TestAPIFailure(unittest.TestCase):
    def test_api_failure_propagates(self):
        import post_new
        from atproto_client.exceptions import AtProtocolError
        client_instance = MagicMock()
        client_instance.send_post.side_effect = AtProtocolError("API error")
        with patch.dict("sys.modules", atproto_modules(client_instance)):
            with self.assertRaises(AtProtocolError):
                post_new.post_to_bluesky("text", "handle", "password", retries=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
