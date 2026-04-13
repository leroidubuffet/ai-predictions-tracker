#!/usr/bin/env python3
"""
Tests for reminders.py
Run: python scripts/reminders_test.py
"""

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent))
import reminders
from reminders import (
    build_reminder_post, truncate_to_fit, parse_deadline,
    already_reminded, mark_reminded, run, BLUESKY_CHAR_LIMIT,
)

REPO_ROOT = Path(__file__).parent.parent
TODAY = date.today()


def make_prediction(days_from_now=30, **kwargs):
    deadline = (TODAY + timedelta(days=days_from_now)).isoformat()
    base = {
        "_filename": "2024-03-15-test-source.yaml",
        "prediction_date": "2024-03-15",
        "source_name": "Test Source",
        "prediction_text": "AI will surpass human intelligence within the next few years.",
        "deadline": deadline,
        "deadline_fuzzy": "",
        "category": "agi",
        "status": "pending",
        "skip_post": False,
    }
    base.update(kwargs)
    return base


def empty_state():
    return {"reminders": {}}


class TestParseDeadline(unittest.TestCase):
    def test_iso_string(self):
        result = parse_deadline("2027-12-31")
        self.assertEqual(result, date(2027, 12, 31))

    def test_date_object(self):
        d = date(2027, 12, 31)
        self.assertEqual(parse_deadline(d), d)

    def test_none(self):
        self.assertIsNone(parse_deadline(None))

    def test_empty_string(self):
        self.assertIsNone(parse_deadline(""))

    def test_invalid_string(self):
        self.assertIsNone(parse_deadline("next year"))

    def test_unparseable_does_not_crash(self):
        # Must return None, not raise
        result = parse_deadline("sometime soon")
        self.assertIsNone(result)


class TestStateManagement(unittest.TestCase):
    def test_already_reminded_false_when_empty(self):
        state = empty_state()
        self.assertFalse(already_reminded(state, "file.yaml", 30))

    def test_mark_reminded_records_threshold(self):
        state = empty_state()
        mark_reminded(state, "file.yaml", 30)
        self.assertTrue(already_reminded(state, "file.yaml", 30))

    def test_already_reminded_different_threshold(self):
        state = empty_state()
        mark_reminded(state, "file.yaml", 30)
        self.assertFalse(already_reminded(state, "file.yaml", 7))

    def test_mark_reminded_idempotent(self):
        state = empty_state()
        mark_reminded(state, "file.yaml", 7)
        mark_reminded(state, "file.yaml", 7)  # second call should not duplicate
        self.assertEqual(state["reminders"]["file.yaml"].count(7), 1)

    def test_multiple_thresholds_tracked_independently(self):
        state = empty_state()
        mark_reminded(state, "file.yaml", 30)
        mark_reminded(state, "file.yaml", 7)
        self.assertTrue(already_reminded(state, "file.yaml", 30))
        self.assertTrue(already_reminded(state, "file.yaml", 7))
        self.assertFalse(already_reminded(state, "file.yaml", 1))


class TestBuildReminderPost(unittest.TestCase):
    def test_within_char_limit(self):
        p = make_prediction(30)
        post = build_reminder_post(p, 30)
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_contains_source(self):
        p = make_prediction(source_name="Geoffrey Hinton")
        post = build_reminder_post(p, 30)
        self.assertIn("Geoffrey Hinton", post)

    def test_contains_days_countdown_30(self):
        p = make_prediction()
        post = build_reminder_post(p, 30)
        self.assertIn("30 days", post)

    def test_contains_days_countdown_7(self):
        p = make_prediction()
        post = build_reminder_post(p, 7)
        self.assertIn("7 days", post)

    def test_one_day_says_tomorrow(self):
        p = make_prediction()
        post = build_reminder_post(p, 1)
        self.assertIn("Tomorrow", post)
        self.assertNotIn("1 days", post)

    def test_contains_prediction_excerpt(self):
        p = make_prediction(prediction_text="AGI will arrive soon.")
        post = build_reminder_post(p, 30)
        self.assertIn("AGI will arrive soon.", post)

    def test_fuzzy_deadline_used(self):
        p = make_prediction(deadline_fuzzy="by end of 2027")
        post = build_reminder_post(p, 30)
        self.assertIn("by end of 2027", post)

    def test_long_text_truncated_within_limit(self):
        p = make_prediction(prediction_text="word " * 100)
        post = build_reminder_post(p, 30)
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_all_seed_predictions_within_char_limit(self):
        import yaml
        failures = []
        for path in sorted(REPO_ROOT.glob("predictions/*.yaml")):
            if path.name == ".gitkeep":
                continue
            with open(path) as f:
                prediction = yaml.safe_load(f)
            prediction["_filename"] = path.name
            if not prediction.get("deadline"):
                continue
            for threshold in [30, 7, 1]:
                post = build_reminder_post(prediction, threshold)
                if len(post) > BLUESKY_CHAR_LIMIT:
                    failures.append(f"{path.name} ({threshold}d): {len(post)} chars")
        if failures:
            self.fail("Reminder posts exceed char limit:\n" + "\n".join(failures))


class TestRunLogic(unittest.TestCase):
    """Tests for the run() function using mocked Bluesky API and state."""

    def _run_with_mock(self, predictions, today, dry_run=False, initial_state=None):
        """Helper: patches load_predictions, load_state, save_state, post_to_bluesky."""
        state = initial_state if initial_state is not None else empty_state()
        saved_states = []

        with patch.object(reminders, "load_predictions", return_value=predictions), \
             patch.object(reminders, "load_state", return_value=state), \
             patch.object(reminders, "save_state", side_effect=lambda s: saved_states.append(dict(s))), \
             patch.object(reminders, "post_to_bluesky") as mock_post, \
             patch.dict("os.environ", {"BLUESKY_HANDLE": "bot.bsky.social", "BLUESKY_APP_PASSWORD": "pw"}):
            count = run(today=today, dry_run=dry_run)

        return count, mock_post, state, saved_states

    def test_prediction_at_exactly_30_days_triggers(self):
        p = make_prediction(days_from_now=30)
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 1)
        mock_post.assert_called_once()

    def test_prediction_at_29_days_does_not_trigger_30d(self):
        p = make_prediction(days_from_now=29)
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 0)
        mock_post.assert_not_called()

    def test_prediction_at_7_days_triggers(self):
        p = make_prediction(days_from_now=7)
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 1)
        mock_post.assert_called_once()

    def test_prediction_at_1_day_triggers(self):
        p = make_prediction(days_from_now=1)
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 1)
        mock_post.assert_called_once()

    def test_already_reminded_not_re_posted(self):
        p = make_prediction(days_from_now=30)
        initial = {"reminders": {p["_filename"]: [30]}}
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY, initial_state=initial)
        self.assertEqual(count, 0)
        mock_post.assert_not_called()

    def test_status_expired_skipped(self):
        p = make_prediction(days_from_now=30, status="expired")
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 0)
        mock_post.assert_not_called()

    def test_status_notable_skipped(self):
        p = make_prediction(days_from_now=30, status="notable")
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 0)
        mock_post.assert_not_called()

    def test_skip_post_true_skipped(self):
        p = make_prediction(days_from_now=30, skip_post=True)
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 0)
        mock_post.assert_not_called()

    def test_no_deadline_skipped(self):
        p = make_prediction(days_from_now=30)
        p["deadline"] = ""
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 0)
        mock_post.assert_not_called()

    def test_unparseable_deadline_skipped_without_crash(self):
        p = make_prediction(days_from_now=30)
        p["deadline"] = "next decade"
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 0)
        mock_post.assert_not_called()

    def test_multiple_thresholds_same_run_both_fire(self):
        """Two predictions, one at 30d and one at 7d — both fire in one run."""
        p30 = make_prediction(days_from_now=30, _filename="a.yaml")
        p7 = make_prediction(days_from_now=7, _filename="b.yaml")
        count, mock_post, _, _ = self._run_with_mock([p30, p7], today=TODAY)
        self.assertEqual(count, 2)
        self.assertEqual(mock_post.call_count, 2)

    def test_state_written_after_posting(self):
        p = make_prediction(days_from_now=30)
        _, _, _, saved = self._run_with_mock([p], today=TODAY)
        self.assertEqual(len(saved), 1)
        self.assertIn(30, saved[0]["reminders"].get(p["_filename"], []))

    def test_dry_run_does_not_post(self):
        p = make_prediction(days_from_now=30)
        count, mock_post, _, saved = self._run_with_mock([p], today=TODAY, dry_run=True)
        mock_post.assert_not_called()
        self.assertEqual(count, 1)  # counted but not posted
        self.assertEqual(len(saved), 0)  # state not written

    def test_dry_run_does_not_write_state(self):
        p = make_prediction(days_from_now=7)
        _, _, _, saved = self._run_with_mock([p], today=TODAY, dry_run=True)
        self.assertEqual(saved, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
