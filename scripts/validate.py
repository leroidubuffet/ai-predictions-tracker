#!/usr/bin/env python3
"""
Validates prediction YAML files against the project schema.
Usage: validate.py [file ...] — validates specific files
       validate.py            — validates all files in predictions/
Exits non-zero if any file fails validation.
"""

import sys
import re
from pathlib import Path
from datetime import date

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

REPO_ROOT = Path(__file__).parent.parent
PREDICTIONS_DIR = REPO_ROOT / "predictions"
CATEGORIES_FILE = REPO_ROOT / "categories.yaml"

REQUIRED_FIELDS = [
    "prediction_date",
    "source_name",
    "prediction_text",
    "category",
    "status",
    "skip_post",
]
VALID_STATUSES = {"pending", "expired", "notable"}
FILENAME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.yaml$")


def load_valid_categories():
    if not CATEGORIES_FILE.exists():
        print(f"ERROR: {CATEGORIES_FILE} not found", file=sys.stderr)
        sys.exit(2)
    with open(CATEGORIES_FILE) as f:
        data = yaml.safe_load(f)
    return set(data.get("categories", []))


def validate_iso_date(value, field_name):
    """Returns an error string if value is not a valid ISO date, else None."""
    if not isinstance(value, str):
        # PyYAML may parse a bare date as a date object
        if isinstance(value, date):
            return None
        return f"  {field_name}: expected ISO date string, got {type(value).__name__}"
    if not value:
        return None  # empty string means not set, which is allowed for optional fields
    try:
        date.fromisoformat(value)
    except ValueError:
        return f"  {field_name}: '{value}' is not a valid ISO date (expected YYYY-MM-DD)"
    return None


def validate_file(path, valid_categories):
    errors = []
    path = Path(path)

    # Filename format
    if not FILENAME_PATTERN.match(path.name):
        errors.append(f"  filename: '{path.name}' must match YYYY-MM-DD-*.yaml")

    # Parse YAML
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"  YAML parse error: {e}"]

    if not isinstance(data, dict):
        return ["  file does not contain a YAML mapping"]

    # Required fields present and non-empty
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"  {field}: missing required field")
        elif field == "skip_post":
            if not isinstance(data[field], bool):
                errors.append(f"  skip_post: must be a boolean (true/false), got {type(data[field]).__name__}")
        elif field != "prediction_date":  # prediction_date checked separately below
            value = data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                errors.append(f"  {field}: must not be empty")

    # prediction_date: required and valid ISO date
    if "prediction_date" in data:
        err = validate_iso_date(str(data["prediction_date"]) if not isinstance(data["prediction_date"], str) else data["prediction_date"], "prediction_date")
        if err:
            errors.append(err)
        elif data["prediction_date"] is None or data["prediction_date"] == "":
            errors.append("  prediction_date: must not be empty")

    # deadline: optional but must be valid ISO date if present and non-empty
    if "deadline" in data and data["deadline"] and data["deadline"] != "":
        deadline_val = data["deadline"]
        if isinstance(deadline_val, date):
            deadline_val = deadline_val.isoformat()
        err = validate_iso_date(str(deadline_val), "deadline")
        if err:
            errors.append(err)

    # category: must be in controlled vocabulary
    if "category" in data and data["category"]:
        if data["category"] not in valid_categories:
            errors.append(f"  category: '{data['category']}' is not in categories.yaml (valid: {sorted(valid_categories)})")

    # status: must be one of the allowed values
    if "status" in data and data["status"]:
        if data["status"] not in VALID_STATUSES:
            errors.append(f"  status: '{data['status']}' must be one of {sorted(VALID_STATUSES)}")

    return errors


def main():
    valid_categories = load_valid_categories()

    if len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:]]
    else:
        files = sorted(PREDICTIONS_DIR.glob("*.yaml"))
        files = [f for f in files if f.name != ".gitkeep"]

    if not files:
        print("No prediction files found.")
        sys.exit(0)

    total = 0
    failed = 0
    for path in files:
        total += 1
        errors = validate_file(path, valid_categories)
        if errors:
            failed += 1
            print(f"FAIL {path.name}")
            for e in errors:
                print(e)
        else:
            print(f"OK   {path.name}")

    print(f"\n{total - failed}/{total} files valid")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
