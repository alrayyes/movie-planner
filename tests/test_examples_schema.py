"""examples/movies.schema.json documents the row shape movie-planner's own
import accepts, for movie-planner-web and any other external reader. These
tests keep it honest against the example files it's meant to describe -
not against the parser itself, which tests/test_import.py already covers.
"""

import csv
import json
from pathlib import Path
from typing import cast

import jsonschema
import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


@pytest.fixture
def schema() -> dict[str, object]:
    raw = json.loads((EXAMPLES_DIR / "movies.schema.json").read_text(encoding="utf-8"))
    return cast(dict[str, object], raw)


@pytest.fixture
def row_schema(schema: dict[str, object]) -> dict[str, object]:
    return {**schema["$defs"]["row"], "$defs": schema["$defs"]}  # type: ignore[index]


def test_schema_is_itself_valid(schema: dict[str, object]) -> None:
    jsonschema.Draft202012Validator.check_schema(schema)


def test_movies_json_validates_against_the_schema(schema: dict[str, object]) -> None:
    rows = json.loads((EXAMPLES_DIR / "movies.json").read_text(encoding="utf-8"))

    jsonschema.validate(rows, schema)


def test_movies_csv_rows_validate_against_the_schema(row_schema: dict[str, object]) -> None:
    with (EXAMPLES_DIR / "movies.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert rows, "movies.csv has no data rows to validate"
    for row in rows:
        # An empty CSV cell means "not supplied", same as the importer's
        # own `raw.get(field) or None` - not the empty string the schema's
        # field types don't accept.
        present = {k: v for k, v in row.items() if v}
        jsonschema.validate(present, row_schema)


def test_a_row_missing_a_required_field_fails_validation(row_schema: dict[str, object]) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"title": "Some Movie", "medium": "cinema"}, row_schema)


def test_a_non_numeral_release_year_fails_validation(row_schema: dict[str, object]) -> None:
    row = {"title": "Some Movie", "date": "2026-01-01", "medium": "cinema", "release_year": "N/A"}

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(row, row_schema)


def test_a_row_with_a_source_field_validates(row_schema: dict[str, object]) -> None:
    row = {"title": "Some Movie", "date": "2026-01-01", "medium": "cinema", "source": "pathe.nl"}

    jsonschema.validate(row, row_schema)


def test_the_schema_no_longer_defines_booking_ref(schema: dict[str, object]) -> None:
    row_def = schema["$defs"]["row"]  # type: ignore[index]
    assert "booking_ref" not in row_def["properties"]
