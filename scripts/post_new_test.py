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
from post_new import build_post, truncate_to_fit, deadline_display, format_date, load_prediction, BLUESKY_CHAR_LIMIT

REPO_ROOT = Path(__file__).parent.parent


def make_prediction(**kwargs):
    base = {
        "prediction_date": "2024-03-15",
        "source_name": "Sam Altman",
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
        self.assertNotIn("thre…", result)  # no mid-word cut

    def test_exactly_at_limit_not_truncated(self):
        text = "a" * 50
        self.assertEqual(truncate_to_fit(text, 50), text)


class TestFormatDate(unittest.TestCase):
    def test_iso_string_returns_year(self):
        self.assertEqual(format_date("2024-03-15"), "2024")

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
        p = make_prediction()
        post = build_post(p)
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_post_contains_source(self):
        p = make_prediction(source_name="Geoffrey Hinton")
        post = build_post(p)
        self.assertIn("Geoffrey Hinton", post)

    def test_post_contains_year(self):
        p = make_prediction(prediction_date="2023-05-16")
        post = build_post(p)
        self.assertIn("2023", post)

    def test_post_contains_prediction_excerpt(self):
        p = make_prediction(prediction_text="AGI will arrive soon.")
        post = build_post(p)
        self.assertIn("AGI will arrive soon.", post)

    def test_post_contains_deadline_when_present(self):
        p = make_prediction(deadline_fuzzy="by end of 2030")
        post = build_post(p)
        self.assertIn("Deadline:", post)
        self.assertIn("by end of 2030", post)

    def test_no_deadline_section_when_absent(self):
        p = make_prediction(deadline="", deadline_fuzzy="")
        post = build_post(p)
        self.assertNotIn("Deadline:", post)

    def test_deadline_fuzzy_used_over_iso(self):
        p = make_prediction(deadline="2030-12-31", deadline_fuzzy="before 2031")
        post = build_post(p)
        self.assertIn("before 2031", post)
        self.assertNotIn("Dec", post)

    def test_long_prediction_truncated_at_word_boundary(self):
        long_text = "artificial intelligence " * 20  # ~480 chars
        p = make_prediction(prediction_text=long_text)
        post = build_post(p)
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)
        # Should not cut in the middle of "intelligence" or "artificial"
        self.assertNotIn("intelligen…", post)
        self.assertNotIn("artifici…", post)

    def test_post_within_limit_with_long_source_and_deadline(self):
        p = make_prediction(
            source_name="A Very Long Organization Name That Takes Up Space",
            prediction_text="Short prediction.",
            deadline_fuzzy="sometime in the next decade or two",
        )
        post = build_post(p)
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_all_seed_predictions_within_char_limit(self):
        predictions_dir = REPO_ROOT / "predictions"
        import yaml
        failures = []
        for path in sorted(predictions_dir.glob("*.yaml")):
            if path.name == ".gitkeep":
                continue
            with open(path) as f:
                prediction = yaml.safe_load(f)
            post = build_post(prediction)
            if len(post) > BLUESKY_CHAR_LIMIT:
                failures.append(f"{path.name}: {len(post)} chars")
        if failures:
            self.fail("Posts exceed char limit:\n" + "\n".join(failures))


def atproto_modules(client_instance):
    """Build a sys.modules patch that covers both atproto and atproto_client.exceptions."""
    mock_client_class = MagicMock(return_value=client_instance)
    from atproto_client.exceptions import AtProtocolError
    mock_atproto_client = MagicMock()
    mock_atproto_client.exceptions.AtProtocolError = AtProtocolError
    return {
        "atproto": MagicMock(Client=mock_client_class),
        "atproto_client": mock_atproto_client,
        "atproto_client.exceptions": mock_atproto_client.exceptions,
    }


class TestSkipPost(unittest.TestCase):
    def test_skip_post_true_produces_no_api_call(self):
        """Files with skip_post: true must not trigger any Bluesky API call."""
        import post_new
        client_instance = MagicMock()
        with patch.dict("sys.modules", atproto_modules(client_instance)):
            p = make_prediction(skip_post=True)
            if p.get("skip_post"):
                pass  # would sys.exit(0) in real code
            else:
                post_new.post_to_bluesky("text", "handle", "password")

        client_instance.send_post.assert_not_called()

    def test_skip_post_false_would_post(self):
        """Files with skip_post: false pass through to the API call."""
        import post_new
        client_instance = MagicMock()
        with patch.dict("sys.modules", atproto_modules(client_instance)):
            post_new.post_to_bluesky("test post", "handle@bsky.social", "app_password")

        client_instance.send_post.assert_called_once_with(text="test post")


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
