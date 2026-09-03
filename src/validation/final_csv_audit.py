from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import urlparse

from src.config import FINAL_DATA_DIR, ensure_directories


INPUT_FILE = FINAL_DATA_DIR / "models_final.csv"
REPORT_FILE = FINAL_DATA_DIR / "final_csv_audit_report.txt"


CRITICAL_COLUMNS = [
    "Model Name",
    "Model Family",
    "Company / Provider",
    "Description",
    "Quality Score",
    "Quality Band",
    "Source URLs",
]


URL_COLUMNS = [
    "Official Website",
    "Hugging Face",
    "GitHub",
    "Documentation",
]


def is_empty(value: str) -> bool:
    return value is None or not str(value).strip()


def split_values(value: str) -> list[str]:
    if not value or not value.strip():
        return []

    return [
        item.strip()
        for item in value.split(";")
        if item.strip()
    ]


def valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.netloc)
        )

    except Exception:
        return False


def main() -> None:
    ensure_directories()

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"CSV file not found: {INPUT_FILE}"
        )

    with INPUT_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        reader = csv.DictReader(f)

        rows = list(reader)
        columns = reader.fieldnames or []

    errors = []
    warnings = []

    # ---------------------------------------------------------
    # Basic structure
    # ---------------------------------------------------------

    if not rows:
        errors.append("CSV contains zero records.")

    if len(rows) != 41:
        warnings.append(
            f"Expected 41 records, found {len(rows)}."
        )

    # ---------------------------------------------------------
    # Required columns
    # ---------------------------------------------------------

    missing_columns = [
        column
        for column in CRITICAL_COLUMNS
        if column not in columns
    ]

    if missing_columns:
        errors.append(
            "Missing critical columns: "
            + ", ".join(missing_columns)
        )

    # ---------------------------------------------------------
    # Duplicate model names
    # ---------------------------------------------------------

    model_names = [
        row.get("Model Name", "").strip()
        for row in rows
    ]

    duplicates = sorted(
        {
            name
            for name in model_names
            if name
            and model_names.count(name) > 1
        }
    )

    if duplicates:
        errors.append(
            "Duplicate Model Name values: "
            + ", ".join(duplicates)
        )

    # ---------------------------------------------------------
    # Row-level checks
    # ---------------------------------------------------------

    missing_critical = {}

    for index, row in enumerate(rows, start=2):

        missing = []

        for column in CRITICAL_COLUMNS:
            if is_empty(row.get(column, "")):
                missing.append(column)

        if missing:
            missing_critical[index] = missing

    if missing_critical:
        warnings.append(
            f"{len(missing_critical)} rows have missing "
            "critical fields."
        )

    # ---------------------------------------------------------
    # Description checks
    # ---------------------------------------------------------

    description_word_counts = []
    description_problems = {}

    banned_phrases = [
        "revolutionary",
        "game-changing",
        "world-class",
        "best model",
        "according to the source",
    ]

    for index, row in enumerate(rows, start=2):

        description = (
            row.get("Description", "")
            .strip()
        )

        word_count = len(
            description.split()
        )

        description_word_counts.append(
            word_count
        )

        problems = []

        if not description:
            problems.append("empty")

        if word_count < 30:
            problems.append("too_short")

        if word_count > 130:
            problems.append("too_long")

        lower = description.lower()

        if "\n" in description:
            problems.append("multiple_lines")

        if "http://" in lower or "https://" in lower:
            problems.append("contains_url")

        for phrase in banned_phrases:
            if phrase in lower:
                problems.append(
                    f"banned_phrase:{phrase}"
                )

        if problems:
            description_problems[index] = problems

    if description_problems:
        errors.append(
            f"{len(description_problems)} rows have "
            "description validation problems."
        )

    # ---------------------------------------------------------
    # Quality Score
    # ---------------------------------------------------------

    invalid_scores = {}

    for index, row in enumerate(rows, start=2):

        raw_score = (
            row.get("Quality Score", "")
            .strip()
        )

        try:
            score = float(raw_score)

            if not 0 <= score <= 100:
                invalid_scores[index] = (
                    "score_out_of_range"
                )

        except ValueError:
            invalid_scores[index] = (
                "invalid_score"
            )

    if invalid_scores:
        errors.append(
            f"{len(invalid_scores)} rows have invalid "
            "Quality Score values."
        )

    # ---------------------------------------------------------
    # URL checks
    # ---------------------------------------------------------

    invalid_urls = {}

    for index, row in enumerate(rows, start=2):

        row_invalid = []

        for column in URL_COLUMNS + ["Source URLs"]:

            values = split_values(
                row.get(column, "")
            )

            for value in values:

                if not valid_url(value):
                    row_invalid.append(
                        f"{column}:{value}"
                    )

        if row_invalid:
            invalid_urls[index] = row_invalid

    if invalid_urls:
        warnings.append(
            f"{len(invalid_urls)} rows contain invalid URL values."
        )

    # ---------------------------------------------------------
    # Coverage statistics
    # ---------------------------------------------------------

    coverage = {}

    for column in columns:

        present = sum(
            not is_empty(
                row.get(column, "")
            )
            for row in rows
        )

        coverage[column] = {
            "present": present,
            "missing": len(rows) - present,
            "percentage": round(
                present / len(rows) * 100,
                2,
            )
            if rows
            else 0,
        }

    # ---------------------------------------------------------
    # Final status
    # ---------------------------------------------------------

    valid = len(errors) == 0

    lines = [
        "AIOrbit Models - Final CSV Audit",
        f"Input CSV: {INPUT_FILE}",
        f"Records: {len(rows)}",
        f"Columns: {len(columns)}",
        "",
        f"VALID: {valid}",
        "",
        "STRUCTURE",
        "=" * 90,
        f"Expected records: 41",
        f"Actual records: {len(rows)}",
        f"Duplicate model names: {len(duplicates)}",
        f"Missing critical column count: {len(missing_columns)}",
        "",
        "DESCRIPTION",
        "=" * 90,
        f"Minimum words: "
        f"{min(description_word_counts) if description_word_counts else 0}",
        f"Maximum words: "
        f"{max(description_word_counts) if description_word_counts else 0}",
        f"Average words: "
        f"{round(sum(description_word_counts) / len(description_word_counts), 2) if description_word_counts else 0}",
        f"Description problem rows: "
        f"{len(description_problems)}",
        "",
        "QUALITY SCORE",
        "=" * 90,
        f"Invalid score rows: {len(invalid_scores)}",
        "",
        "URL CHECK",
        "=" * 90,
        f"Rows containing invalid URLs: {len(invalid_urls)}",
        "",
        "COLUMN COVERAGE",
        "=" * 90,
    ]

    for column, stats in coverage.items():

        lines.append(
            f"{column:<30} "
            f"{stats['present']:>2}/{len(rows):<2} "
            f"{stats['percentage']:>6.2f}%"
        )

    lines.extend(
        [
            "",
            "ERRORS",
            "=" * 90,
        ]
    )

    if errors:
        lines.extend(
            f"- {error}"
            for error in errors
        )
    else:
        lines.append("None")

    lines.extend(
        [
            "",
            "WARNINGS",
            "=" * 90,
        ]
    )

    if warnings:
        lines.extend(
            f"- {warning}"
            for warning in warnings
        )
    else:
        lines.append("None")

    REPORT_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print(
        f"Records: {len(rows)}"
    )

    print(
        f"Columns: {len(columns)}"
    )

    print(
        f"Duplicate model names: "
        f"{len(duplicates)}"
    )

    print(
        f"Description problem rows: "
        f"{len(description_problems)}"
    )

    print(
        f"Invalid score rows: "
        f"{len(invalid_scores)}"
    )

    print(
        f"Invalid URL rows: "
        f"{len(invalid_urls)}"
    )

    print(
        f"Errors: {len(errors)}"
    )

    print(
        f"Warnings: {len(warnings)}"
    )

    print(
        f"CSV valid: {valid}"
    )

    print(
        f"Report: {REPORT_FILE}"
    )


if __name__ == "__main__":
    main()