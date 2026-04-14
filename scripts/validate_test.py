#!/usr/bin/env python3
"""
Tests for validate.py
Run: python scripts/validate_test.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

# Allow importing validate from the same directory
sys.path.insert(0, str(Path(__file__).parent))
from validate import validate_file, load_valid_categories, FILENAME_PATTERN

REPO_ROOT = Path(__file__).parent.parent

# Load real categories and source_types for tests
VALID_CATEGORIES, VALID_SOURCE_TYPES = load_valid_categories()

VALID_YAML = """prediction_date: "2024-03-15"
source_name: "Test Source"
source_url: "https://example.com"
prediction_text: |
  This is a test prediction with meaningful content.
deadline: "2027-12-31"
deadline_fuzzy: "by end of 2027"
category: agi
source_type: researcher
conflict_of_interest: false
status: pending
notes: |
  Some notes here.
skip_post: true
"""


def write_temp(content, filename="2024-03-15-test-source.yaml"):
    """Write content to a temp file with the given filename, return Path."""
    d = tempfile.mkdtemp()
    p = Path(d) / filename
    p.write_text(content)
    return p


class TestFilenamePattern(unittest.TestCase):
    def test_valid_filename(self):
        self.assertRegex("2024-03-15-sam-altman.yaml", FILENAME_PATTERN)

    def test_valid_filename_with_numbers(self):
        self.assertRegex("2024-03-15-gpt4-capabilities.yaml", FILENAME_PATTERN)

    def test_missing_date(self):
        self.assertNotRegex("sam-altman.yaml", FILENAME_PATTERN)

    def test_wrong_extension(self):
        self.assertNotRegex("2024-03-15-sam-altman.yml", FILENAME_PATTERN)

    def test_no_slug(self):
        self.assertNotRegex("2024-03-15-.yaml", FILENAME_PATTERN)

    def test_wrong_date_format(self):
        self.assertNotRegex("24-03-15-sam-altman.yaml", FILENAME_PATTERN)


class TestValidFile(unittest.TestCase):
    def test_valid_file_passes(self):
        p = write_temp(VALID_YAML)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertEqual(errors, [], f"Expected no errors, got: {errors}")

    def test_valid_file_without_optional_fields(self):
        content = """prediction_date: "2024-03-15"
source_name: "Test Source"
prediction_text: |
  Prediction content.
category: agi
source_type: practitioner
conflict_of_interest: false
status: pending
skip_post: false
"""
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertEqual(errors, [])

    def test_valid_status_expired(self):
        content = VALID_YAML.replace("status: pending", "status: expired")
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertEqual(errors, [])

    def test_valid_status_notable(self):
        content = VALID_YAML.replace("status: pending", "status: notable")
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertEqual(errors, [])

    def test_skip_post_false(self):
        content = VALID_YAML.replace("skip_post: true", "skip_post: false")
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertEqual(errors, [])

    def test_empty_optional_deadline(self):
        content = VALID_YAML.replace('deadline: "2027-12-31"', 'deadline: ""')
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertEqual(errors, [])

    def test_all_valid_categories(self):
        for cat in VALID_CATEGORIES:
            content = VALID_YAML.replace("category: agi", f"category: {cat}")
            p = write_temp(content)
            errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
            self.assertEqual(errors, [], f"Category '{cat}' should be valid")


class TestMissingRequiredFields(unittest.TestCase):
    def _remove_field(self, field_line_prefix):
        lines = VALID_YAML.splitlines()
        filtered = [l for l in lines if not l.startswith(field_line_prefix)]
        return "\n".join(filtered) + "\n"

    def test_missing_prediction_date(self):
        content = self._remove_field("prediction_date:")
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("prediction_date" in e for e in errors))

    def test_missing_source_name(self):
        content = self._remove_field("source_name:")
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("source_name" in e for e in errors))

    def test_missing_category(self):
        content = self._remove_field("category:")
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("category" in e for e in errors))

    def test_missing_status(self):
        content = self._remove_field("status:")
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("status" in e for e in errors))

    def test_missing_prediction_text(self):
        # prediction_text is multiline, remove the key and its value
        lines = VALID_YAML.splitlines()
        filtered = []
        skip = False
        for line in lines:
            if line.startswith("prediction_text:"):
                skip = True
                continue
            if skip and (line.startswith(" ") or line == ""):
                continue
            skip = False
            filtered.append(line)
        content = "\n".join(filtered) + "\n"
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("prediction_text" in e for e in errors))

    def test_missing_skip_post(self):
        content = self._remove_field("skip_post:")
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("skip_post" in e for e in errors))


class TestInvalidFieldValues(unittest.TestCase):
    def test_invalid_category(self):
        content = VALID_YAML.replace("category: agi", "category: robots")
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("category" in e for e in errors))

    def test_invalid_status(self):
        content = VALID_YAML.replace("status: pending", "status: done")
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("status" in e for e in errors))

    def test_malformed_deadline(self):
        content = VALID_YAML.replace('deadline: "2027-12-31"', 'deadline: "next year"')
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("deadline" in e for e in errors))

    def test_malformed_prediction_date(self):
        content = VALID_YAML.replace('prediction_date: "2024-03-15"', 'prediction_date: "15/03/2024"')
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("prediction_date" in e for e in errors))

    def test_skip_post_as_string(self):
        content = VALID_YAML.replace("skip_post: true", 'skip_post: "true"')
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("skip_post" in e for e in errors))

    def test_empty_source_name(self):
        content = VALID_YAML.replace('source_name: "Test Source"', 'source_name: ""')
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("source_name" in e for e in errors))

    def test_invalid_source_type(self):
        content = VALID_YAML.replace("source_type: researcher", "source_type: celebrity")
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("source_type" in e for e in errors))

    def test_conflict_of_interest_as_string(self):
        content = VALID_YAML.replace("conflict_of_interest: false", 'conflict_of_interest: "false"')
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("conflict_of_interest" in e for e in errors))

    def test_all_valid_source_types(self):
        for st in VALID_SOURCE_TYPES:
            content = VALID_YAML.replace("source_type: researcher", f"source_type: {st}")
            p = write_temp(content)
            errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
            self.assertEqual(errors, [], f"source_type '{st}' should be valid")

    def test_conflict_of_interest_true_is_valid(self):
        content = VALID_YAML.replace("conflict_of_interest: false", "conflict_of_interest: true")
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertEqual(errors, [])


class TestMissingSourceFields(unittest.TestCase):
    def test_missing_source_type(self):
        lines = [l for l in VALID_YAML.splitlines() if not l.startswith("source_type:")]
        content = "\n".join(lines) + "\n"
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("source_type" in e for e in errors))

    def test_missing_conflict_of_interest(self):
        lines = [l for l in VALID_YAML.splitlines() if not l.startswith("conflict_of_interest:")]
        content = "\n".join(lines) + "\n"
        p = write_temp(content)
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("conflict_of_interest" in e for e in errors))


class TestFilenameValidation(unittest.TestCase):
    def test_badly_named_file_fails(self):
        p = write_temp(VALID_YAML, filename="agi-prediction.yaml")
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("filename" in e for e in errors))

    def test_wrong_extension_fails(self):
        p = write_temp(VALID_YAML, filename="2024-03-15-test.yml")
        errors = validate_file(p, VALID_CATEGORIES, VALID_SOURCE_TYPES)
        self.assertTrue(any("filename" in e for e in errors))


class TestSeedPredictions(unittest.TestCase):
    """Validate all seed predictions in the predictions/ directory."""

    def test_all_seed_predictions_valid(self):
        predictions_dir = REPO_ROOT / "predictions"
        files = sorted(predictions_dir.glob("*.yaml"))
        files = [f for f in files if f.name != ".gitkeep"]
        self.assertGreater(len(files), 0, "No prediction files found")
        all_errors = {}
        for f in files:
            errors = validate_file(f, VALID_CATEGORIES, VALID_SOURCE_TYPES)
            if errors:
                all_errors[f.name] = errors
        if all_errors:
            msg = "\n".join(
                f"{name}:\n" + "\n".join(errs)
                for name, errs in all_errors.items()
            )
            self.fail(f"Seed prediction validation failures:\n{msg}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
