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
    build_reminder_post, build_expired_post, build_anniversary_post,
    build_elapsed_post, get_elapsed_interval, elapsed_label,
    truncate_to_fit, parse_deadline, already_reminded, mark_reminded, run,
    get_thresholds, get_anniversary_year, get_hashtags,
    prediction_age_label, days_label,
    BLUESKY_CHAR_LIMIT, HASHTAGS, EXPIRED_KEY,
)

REPO_ROOT = Path(__file__).parent.parent
TODAY = date.today()


def make_prediction(days_from_now=30, **kwargs):
    deadline = (TODAY + timedelta(days=days_from_now)).isoformat()
    # Use a recent prediction_date by default so age framing doesn't kick in
    # (< 1 year old, so prediction_age_label returns None)
    prediction_date = (TODAY - timedelta(days=60)).isoformat()
    base = {
        "_filename": "2024-03-15-test-source.yaml",
        "prediction_date": prediction_date,
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


def make_no_deadline_prediction(days_old, importance="low", **kwargs):
    prediction_date = (TODAY - timedelta(days=days_old)).isoformat()
    base = {
        "_filename": "2024-03-15-test-source.yaml",
        "prediction_date": prediction_date,
        "source_name": "Test Source",
        "prediction_text": "AI will surpass human intelligence within the next few years.",
        "deadline": "",
        "deadline_fuzzy": "",
        "category": "capabilities",
        "status": "pending",
        "importance": importance,
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
        mark_reminded(state, "file.yaml", 7)
        self.assertEqual(state["reminders"]["file.yaml"].count(7), 1)

    def test_multiple_thresholds_tracked_independently(self):
        state = empty_state()
        mark_reminded(state, "file.yaml", 30)
        mark_reminded(state, "file.yaml", 7)
        self.assertTrue(already_reminded(state, "file.yaml", 30))
        self.assertTrue(already_reminded(state, "file.yaml", 7))
        self.assertFalse(already_reminded(state, "file.yaml", 1))

    def test_expired_key_tracked(self):
        state = empty_state()
        mark_reminded(state, "file.yaml", EXPIRED_KEY)
        self.assertTrue(already_reminded(state, "file.yaml", EXPIRED_KEY))

    def test_expired_key_independent_of_int_thresholds(self):
        state = empty_state()
        mark_reminded(state, "file.yaml", 30)
        self.assertFalse(already_reminded(state, "file.yaml", EXPIRED_KEY))


class TestGetThresholds(unittest.TestCase):
    def test_short_horizon_base_only(self):
        self.assertEqual(get_thresholds(90), [30, 7, 1])

    def test_one_year_horizon_adds_365(self):
        thresholds = get_thresholds(365)
        self.assertIn(365, thresholds)
        self.assertIn(30, thresholds)
        self.assertIn(7, thresholds)
        self.assertIn(1, thresholds)

    def test_two_year_horizon_adds_730_and_365(self):
        thresholds = get_thresholds(730)
        self.assertIn(730, thresholds)
        self.assertIn(365, thresholds)
        self.assertIn(30, thresholds)

    def test_five_year_horizon_has_all_yearly_milestones(self):
        thresholds = get_thresholds(5 * 365)
        for y in range(1, 6):
            self.assertIn(y * 365, thresholds)

    def test_thresholds_sorted_descending(self):
        thresholds = get_thresholds(730)
        self.assertEqual(thresholds, sorted(thresholds, reverse=True))

    def test_no_duplicates(self):
        thresholds = get_thresholds(365)
        self.assertEqual(len(thresholds), len(set(thresholds)))

    def test_less_than_30_days_horizon_still_has_1(self):
        thresholds = get_thresholds(20)
        self.assertIn(1, thresholds)


class TestPredictionAgeLabel(unittest.TestCase):
    def test_less_than_one_year_returns_none(self):
        today = date(2026, 4, 13)
        self.assertIsNone(prediction_age_label("2025-10-01", today))

    def test_exactly_one_year_returns_label(self):
        today = date(2026, 4, 13)
        result = prediction_age_label("2025-04-01", today)
        self.assertEqual(result, "1 year ago")

    def test_two_years_old(self):
        today = date(2026, 4, 13)
        result = prediction_age_label("2024-04-01", today)
        self.assertEqual(result, "2 years ago")

    def test_three_years_old(self):
        today = date(2026, 4, 13)
        result = prediction_age_label("2023-04-01", today)
        self.assertEqual(result, "3 years ago")

    def test_none_returns_none(self):
        self.assertIsNone(prediction_age_label(None, date.today()))

    def test_empty_string_returns_none(self):
        self.assertIsNone(prediction_age_label("", date.today()))

    def test_invalid_returns_none(self):
        self.assertIsNone(prediction_age_label("not a date", date.today()))

    def test_very_recent_returns_none(self):
        today = date(2026, 4, 13)
        yesterday = (today - timedelta(days=1)).isoformat()
        self.assertIsNone(prediction_age_label(yesterday, today))


class TestDaysLabel(unittest.TestCase):
    def test_1_day_is_tomorrow(self):
        self.assertEqual(days_label(1), "Tomorrow")

    def test_7_days(self):
        self.assertEqual(days_label(7), "7 days")

    def test_30_days(self):
        self.assertEqual(days_label(30), "30 days")

    def test_365_days_is_1_year(self):
        self.assertEqual(days_label(365), "1 year")

    def test_730_days_is_2_years(self):
        self.assertEqual(days_label(730), "2 years")

    def test_1825_days_is_5_years(self):
        self.assertEqual(days_label(1825), "5 years")

    def test_non_yearly_365_multiple_is_days(self):
        self.assertEqual(days_label(400), "400 days")


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

    def test_yearly_milestone_shows_year_label(self):
        p = make_prediction(days_from_now=365)
        post = build_reminder_post(p, 365)
        self.assertIn("1 year", post)

    def test_two_year_milestone_shows_years_label(self):
        p = make_prediction(days_from_now=730)
        post = build_reminder_post(p, 730)
        self.assertIn("2 years", post)

    def test_contains_prediction_excerpt(self):
        p = make_prediction(prediction_text="AGI will arrive soon.")
        post = build_reminder_post(p, 30)
        self.assertIn("AGI will arrive soon.", post)

    def test_fuzzy_deadline_used(self):
        p = make_prediction(deadline_fuzzy="by end of 2027")
        post = build_reminder_post(p, 30)
        self.assertIn("by end of 2027", post)

    def test_hashtags_present(self):
        p = make_prediction()
        post = build_reminder_post(p, 30)
        self.assertIn(HASHTAGS, post)

    def test_no_age_framing_for_recent_prediction(self):
        today = date(2026, 4, 13)
        recent_date = (today - timedelta(days=60)).isoformat()
        p = make_prediction(prediction_date=recent_date)
        post = build_reminder_post(p, 30, today=today)
        self.assertNotIn("ago", post)

    def test_age_framing_for_old_prediction(self):
        today = date(2026, 4, 13)
        old_date = "2024-01-01"
        p = make_prediction(prediction_date=old_date)
        post = build_reminder_post(p, 30, today=today)
        self.assertIn("years ago", post)
        self.assertIn("predicted", post)

    def test_age_framing_within_char_limit(self):
        today = date(2026, 4, 13)
        p = make_prediction(prediction_date="2024-01-01")
        post = build_reminder_post(p, 30, today=today)
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_long_text_truncated_within_limit(self):
        p = make_prediction(prediction_text="word " * 100)
        post = build_reminder_post(p, 30)
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_long_text_with_age_framing_within_limit(self):
        today = date(2026, 4, 13)
        p = make_prediction(prediction_text="word " * 100, prediction_date="2024-01-01")
        post = build_reminder_post(p, 30, today=today)
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
            deadline = parse_deadline(prediction["deadline"])
            pred_date = parse_deadline(prediction.get("prediction_date"))
            horizon = (deadline - pred_date).days if (deadline and pred_date) else 365
            for threshold in get_thresholds(horizon):
                post = build_reminder_post(prediction, threshold)
                if len(post) > BLUESKY_CHAR_LIMIT:
                    failures.append(f"{path.name} ({threshold}d): {len(post)} chars")
        if failures:
            self.fail("Reminder posts exceed char limit:\n" + "\n".join(failures))


class TestBuildExpiredPost(unittest.TestCase):
    def test_within_char_limit(self):
        today = date(2026, 4, 13)
        p = make_prediction(days_from_now=-10, prediction_date="2024-01-01")
        post = build_expired_post(p, today)
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_contains_source(self):
        today = date(2026, 4, 13)
        p = make_prediction(days_from_now=-10, source_name="Elon Musk", prediction_date="2024-01-01")
        post = build_expired_post(p, today)
        self.assertIn("Elon Musk", post)

    def test_indicates_deadline_passed(self):
        today = date(2026, 4, 13)
        p = make_prediction(days_from_now=-10, prediction_date="2024-01-01")
        post = build_expired_post(p, today)
        self.assertIn("passed", post)

    def test_contains_excerpt(self):
        today = date(2026, 4, 13)
        p = make_prediction(
            days_from_now=-10,
            prediction_text="AGI will arrive soon.",
            prediction_date="2024-01-01",
        )
        post = build_expired_post(p, today)
        self.assertIn("AGI will arrive soon.", post)

    def test_hashtags_present(self):
        today = date(2026, 4, 13)
        p = make_prediction(days_from_now=-10, prediction_date="2024-01-01")
        post = build_expired_post(p, today)
        self.assertIn(HASHTAGS, post)

    def test_age_framing_present_for_old_prediction(self):
        today = date(2026, 4, 13)
        p = make_prediction(days_from_now=-10, prediction_date="2024-01-01")
        post = build_expired_post(p, today)
        self.assertIn("years ago", post)
        self.assertIn("predicted", post)

    def test_no_age_framing_for_recent_prediction(self):
        today = date(2026, 4, 13)
        recent = (today - timedelta(days=60)).isoformat()
        p = make_prediction(days_from_now=-10, prediction_date=recent)
        post = build_expired_post(p, today)
        self.assertNotIn("ago", post)

    def test_long_text_within_limit(self):
        today = date(2026, 4, 13)
        p = make_prediction(
            days_from_now=-10,
            prediction_text="word " * 100,
            prediction_date="2024-01-01",
        )
        post = build_expired_post(p, today)
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_fuzzy_deadline_in_post(self):
        today = date(2026, 4, 13)
        p = make_prediction(
            days_from_now=-10,
            deadline_fuzzy="by end of 2025",
            prediction_date="2024-01-01",
        )
        post = build_expired_post(p, today)
        self.assertIn("by end of 2025", post)

    def test_all_seed_expired_predictions_within_char_limit(self):
        import yaml
        today = date.today()
        failures = []
        for path in sorted(REPO_ROOT.glob("predictions/*.yaml")):
            if path.name == ".gitkeep":
                continue
            with open(path) as f:
                prediction = yaml.safe_load(f)
            prediction["_filename"] = path.name
            deadline = parse_deadline(prediction.get("deadline"))
            if deadline is None or deadline >= today:
                continue
            post = build_expired_post(prediction, today)
            if len(post) > BLUESKY_CHAR_LIMIT:
                failures.append(f"{path.name}: {len(post)} chars")
        if failures:
            self.fail("Expired posts exceed char limit:\n" + "\n".join(failures))


class TestGetHashtags(unittest.TestCase):
    def test_default_when_absent(self):
        self.assertEqual(get_hashtags({}), HASHTAGS)

    def test_default_when_empty_string(self):
        self.assertEqual(get_hashtags({"hashtags": ""}), HASHTAGS)

    def test_default_when_none(self):
        self.assertEqual(get_hashtags({"hashtags": None}), HASHTAGS)

    def test_custom_hashtags_returned(self):
        self.assertEqual(get_hashtags({"hashtags": "#AIPredictions #AGI"}), "#AIPredictions #AGI")

    def test_custom_hashtags_in_reminder_post(self):
        p = make_prediction(hashtags="#AIPredictions #AGI")
        post = build_reminder_post(p, 30)
        self.assertIn("#AGI", post)

    def test_custom_hashtags_in_anniversary_post(self):
        p = make_prediction(hashtags="#AIPredictions #Safety")
        post = build_anniversary_post(p, 1)
        self.assertIn("#Safety", post)

    def test_custom_hashtags_in_expired_post(self):
        today = date(2026, 4, 14)
        p = make_prediction(days_from_now=-10, hashtags="#AIPredictions #Timelines", prediction_date="2024-01-01")
        post = build_expired_post(p, today)
        self.assertIn("#Timelines", post)

    def test_custom_hashtags_within_char_limit(self):
        p = make_prediction(hashtags="#AIPredictions #AGI #Timelines #Safety #Alignment")
        post = build_reminder_post(p, 30)
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)


class TestGetAnniversaryYear(unittest.TestCase):
    def test_exactly_one_year(self):
        pred = date(2025, 4, 14)
        today = date(2026, 4, 14)
        self.assertEqual(get_anniversary_year(pred, today), 1)

    def test_exactly_two_years(self):
        pred = date(2024, 4, 14)
        today = date(2026, 4, 14)
        self.assertEqual(get_anniversary_year(pred, today), 2)

    def test_not_anniversary(self):
        pred = date(2025, 4, 14)
        today = date(2026, 4, 15)
        self.assertIsNone(get_anniversary_year(pred, today))

    def test_less_than_one_year(self):
        pred = date(2026, 1, 1)
        today = date(2026, 4, 14)
        self.assertIsNone(get_anniversary_year(pred, today))

    def test_same_day(self):
        today = date(2026, 4, 14)
        self.assertIsNone(get_anniversary_year(today, today))

    def test_none_input(self):
        self.assertIsNone(get_anniversary_year(None, date.today()))

    def test_feb29_fires_on_feb28_in_non_leap_year(self):
        pred = date(2024, 2, 29)  # 2024 is a leap year
        today = date(2025, 2, 28)  # 2025 is not
        self.assertEqual(get_anniversary_year(pred, today), 1)

    def test_feb29_fires_on_feb29_in_leap_year(self):
        pred = date(2020, 2, 29)
        today = date(2024, 2, 29)
        self.assertEqual(get_anniversary_year(pred, today), 4)


class TestBuildAnniversaryPost(unittest.TestCase):
    def test_within_char_limit(self):
        p = make_prediction()
        post = build_anniversary_post(p, 1)
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_one_year_singular(self):
        p = make_prediction(source_name="Geoffrey Hinton")
        post = build_anniversary_post(p, 1)
        self.assertIn("1 year ago", post)
        self.assertNotIn("1 years ago", post)

    def test_two_years_plural(self):
        p = make_prediction(source_name="Geoffrey Hinton")
        post = build_anniversary_post(p, 2)
        self.assertIn("2 years ago", post)

    def test_contains_source(self):
        p = make_prediction(source_name="Yann LeCun")
        post = build_anniversary_post(p, 1)
        self.assertIn("Yann LeCun", post)

    def test_contains_excerpt(self):
        p = make_prediction(prediction_text="LLMs are a dead end.")
        post = build_anniversary_post(p, 1)
        self.assertIn("LLMs are a dead end.", post)

    def test_hashtags_present(self):
        p = make_prediction()
        post = build_anniversary_post(p, 1)
        self.assertIn(HASHTAGS, post)

    def test_long_text_within_limit(self):
        p = make_prediction(prediction_text="word " * 100)
        post = build_anniversary_post(p, 1)
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_no_deadline_needed(self):
        p = make_prediction()
        p["deadline"] = ""
        p["deadline_fuzzy"] = ""
        post = build_anniversary_post(p, 1)
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
            for years in [1, 2, 5]:
                post = build_anniversary_post(prediction, years)
                if len(post) > BLUESKY_CHAR_LIMIT:
                    failures.append(f"{path.name} ({years}y): {len(post)} chars")
        if failures:
            self.fail("Anniversary posts exceed char limit:\n" + "\n".join(failures))


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

    def test_prediction_at_29_days_does_not_trigger(self):
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

    def test_yearly_threshold_fires_for_multi_year_prediction(self):
        # Use a prediction_date that is NOT on an anniversary with TODAY,
        # so only the 365-day threshold fires (not also an anniversary post).
        non_anniversary = date(TODAY.year - 2, TODAY.month, TODAY.day) + timedelta(days=1)
        p = make_prediction(days_from_now=365, prediction_date=non_anniversary.isoformat())
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 1)
        mock_post.assert_called_once()

    def test_expired_prediction_triggers(self):
        p = make_prediction(days_from_now=-5)
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 1)
        mock_post.assert_called_once()

    def test_already_expired_not_reposted(self):
        p = make_prediction(days_from_now=-5)
        initial = {"reminders": {p["_filename"]: [EXPIRED_KEY]}}
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY, initial_state=initial)
        self.assertEqual(count, 0)
        mock_post.assert_not_called()

    def test_expired_state_marked_after_posting(self):
        p = make_prediction(days_from_now=-5)
        _, _, _, saved = self._run_with_mock([p], today=TODAY)
        self.assertIn(EXPIRED_KEY, saved[0]["reminders"].get(p["_filename"], []))

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

    def test_multiple_predictions_both_fire(self):
        p30 = make_prediction(days_from_now=30, **{"_filename": "a.yaml"})
        p7 = make_prediction(days_from_now=7, **{"_filename": "b.yaml"})
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
        self.assertEqual(count, 1)
        self.assertEqual(len(saved), 0)

    def test_dry_run_does_not_write_state(self):
        p = make_prediction(days_from_now=7)
        _, _, _, saved = self._run_with_mock([p], today=TODAY, dry_run=True)
        self.assertEqual(saved, [])

    def test_dry_run_expired_not_posted(self):
        p = make_prediction(days_from_now=-5)
        count, mock_post, _, saved = self._run_with_mock([p], today=TODAY, dry_run=True)
        mock_post.assert_not_called()
        self.assertEqual(count, 1)
        self.assertEqual(len(saved), 0)

    def test_anniversary_fires_on_exact_date(self):
        pred_date = date(TODAY.year - 1, TODAY.month, TODAY.day)
        p = make_prediction(days_from_now=365, prediction_date=pred_date.isoformat())
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertGreaterEqual(count, 1)
        mock_post.assert_called()

    def test_anniversary_not_fired_on_wrong_day(self):
        pred_date = date(TODAY.year - 1, TODAY.month, TODAY.day) - timedelta(days=1)
        p = make_prediction(days_from_now=30, prediction_date=pred_date.isoformat())
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        # May fire for 30d reminder but not anniversary
        anniversary_key = f"anniversary_1"
        # Verify state does NOT contain anniversary key
        _, _, state, saved = self._run_with_mock([p], today=TODAY)
        reminded = saved[0]["reminders"].get(p["_filename"], []) if saved else []
        self.assertNotIn(anniversary_key, reminded)

    def test_elapsed_fires_for_no_deadline_prediction(self):
        p = make_no_deadline_prediction(days_old=365)
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 1)
        mock_post.assert_called_once()

    def test_anniversary_state_marked(self):
        pred_date = date(TODAY.year - 1, TODAY.month, TODAY.day)
        p = make_prediction(days_from_now=400, prediction_date=pred_date.isoformat())
        _, _, _, saved = self._run_with_mock([p], today=TODAY)
        reminded = saved[0]["reminders"].get(p["_filename"], [])
        self.assertIn("anniversary_1", reminded)

    def test_elapsed_not_reposted(self):
        p = make_no_deadline_prediction(days_old=365)
        initial = {"reminders": {p["_filename"]: ["elapsed_365"]}}
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY, initial_state=initial)
        self.assertEqual(count, 0)
        mock_post.assert_not_called()

    def test_dry_run_elapsed_not_posted(self):
        p = make_no_deadline_prediction(days_old=365)
        count, mock_post, _, saved = self._run_with_mock([p], today=TODAY, dry_run=True)
        mock_post.assert_not_called()
        self.assertEqual(count, 1)
        self.assertEqual(len(saved), 0)


class TestElapsedLabel(unittest.TestCase):
    def test_six_months(self):
        self.assertEqual(elapsed_label(183), "6 months")

    def test_one_year(self):
        self.assertEqual(elapsed_label(365), "1 year")

    def test_one_year_high_interval(self):
        self.assertEqual(elapsed_label(366), "1 year")

    def test_eighteen_months(self):
        self.assertEqual(elapsed_label(549), "18 months")

    def test_two_years(self):
        self.assertEqual(elapsed_label(730), "2 years")

    def test_three_years(self):
        self.assertEqual(elapsed_label(1095), "3 years")


class TestGetElapsedInterval(unittest.TestCase):
    def test_high_is_183(self):
        self.assertEqual(get_elapsed_interval("high"), 183)

    def test_low_is_365(self):
        self.assertEqual(get_elapsed_interval("low"), 365)

    def test_unknown_defaults_to_365(self):
        self.assertEqual(get_elapsed_interval("unknown"), 365)


class TestBuildElapsedPost(unittest.TestCase):
    def _make(self, **kwargs):
        p = make_no_deadline_prediction(days_old=365)
        p.update(kwargs)
        return p

    def test_within_char_limit(self):
        post = build_elapsed_post(self._make(), "6 months")
        self.assertLessEqual(len(post), BLUESKY_CHAR_LIMIT)

    def test_contains_age_label(self):
        post = build_elapsed_post(self._make(), "6 months")
        self.assertIn("6 months ago", post)

    def test_contains_source(self):
        post = build_elapsed_post(self._make(source_name="Yann LeCun"), "1 year")
        self.assertIn("Yann LeCun", post)

    def test_contains_predicted(self):
        post = build_elapsed_post(self._make(), "1 year")
        self.assertIn("predicted", post)

    def test_contains_excerpt(self):
        post = build_elapsed_post(self._make(prediction_text="LLMs are a dead end."), "1 year")
        self.assertIn("LLMs are a dead end.", post)

    def test_hashtags_present(self):
        post = build_elapsed_post(self._make(), "1 year")
        self.assertIn(HASHTAGS, post)

    def test_long_text_truncated_within_limit(self):
        post = build_elapsed_post(self._make(prediction_text="word " * 100), "1 year")
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
            if prediction.get("deadline"):
                continue
            for label in ["6 months", "1 year", "18 months", "2 years"]:
                post = build_elapsed_post(prediction, label)
                if len(post) > BLUESKY_CHAR_LIMIT:
                    failures.append(f"{path.name} ({label}): {len(post)} chars")
        if failures:
            self.fail("Elapsed posts exceed char limit:\n" + "\n".join(failures))


class TestElapsedRunLogic(unittest.TestCase):
    def _run_with_mock(self, predictions, today, dry_run=False, initial_state=None):
        state = initial_state if initial_state is not None else {"reminders": {}}
        saved_states = []
        with patch.object(reminders, "load_predictions", return_value=predictions), \
             patch.object(reminders, "load_state", return_value=state), \
             patch.object(reminders, "save_state", side_effect=lambda s: saved_states.append(dict(s))), \
             patch.object(reminders, "post_to_bluesky") as mock_post, \
             patch.dict("os.environ", {"BLUESKY_HANDLE": "bot.bsky.social", "BLUESKY_APP_PASSWORD": "pw"}):
            count = run(today=today, dry_run=dry_run)
        return count, mock_post, state, saved_states

    def test_low_importance_fires_at_one_year(self):
        p = make_no_deadline_prediction(days_old=365, importance="low")
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 1)
        mock_post.assert_called_once()

    def test_low_importance_does_not_fire_at_six_months(self):
        p = make_no_deadline_prediction(days_old=183, importance="low")
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 0)
        mock_post.assert_not_called()

    def test_high_importance_fires_at_six_months(self):
        p = make_no_deadline_prediction(days_old=183, importance="high")
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 1)
        mock_post.assert_called_once()

    def test_high_importance_fires_twice_at_one_year(self):
        p = make_no_deadline_prediction(days_old=366, importance="high")
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 2)
        self.assertEqual(mock_post.call_count, 2)

    def test_elapsed_state_uses_correct_key(self):
        p = make_no_deadline_prediction(days_old=365, importance="low")
        _, _, _, saved = self._run_with_mock([p], today=TODAY)
        reminded = saved[0]["reminders"].get(p["_filename"], [])
        self.assertIn("elapsed_365", reminded)

    def test_elapsed_state_uses_correct_key_high(self):
        p = make_no_deadline_prediction(days_old=183, importance="high")
        _, _, _, saved = self._run_with_mock([p], today=TODAY)
        reminded = saved[0]["reminders"].get(p["_filename"], [])
        self.assertIn("elapsed_183", reminded)

    def test_no_prediction_date_no_post(self):
        p = make_no_deadline_prediction(days_old=365)
        p["prediction_date"] = ""
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 0)
        mock_post.assert_not_called()

    def test_anniversary_does_not_fire_for_no_deadline_prediction(self):
        pred_date = date(TODAY.year - 1, TODAY.month, TODAY.day)
        p = make_no_deadline_prediction(days_old=365, importance="low")
        p["prediction_date"] = pred_date.isoformat()
        _, _, _, saved = self._run_with_mock([p], today=TODAY)
        reminded = saved[0]["reminders"].get(p["_filename"], []) if saved else []
        self.assertNotIn("anniversary_1", reminded)
        self.assertIn("elapsed_365", reminded)

    def test_default_importance_is_low(self):
        p = make_no_deadline_prediction(days_old=365)
        del p["importance"]
        count, mock_post, _, _ = self._run_with_mock([p], today=TODAY)
        self.assertEqual(count, 1)
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
