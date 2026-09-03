import json
from collections import Counter


PATH = "data/intermediate/models_dev_normalized.json"


def main() -> None:
    with open(PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    print(f"Total records: {len(data)}")

    fields = [
        "model_id",
        "model_name",
        "model_family",
        "description",
        "release_date",
        "last_updated",
        "reasoning",
        "tool_calling",
        "structured_output",
        "modalities",
        "open_weights",
        "context_window",
        "maximum_output",
        "providers",
        "weights",
        "benchmarks",
    ]

    print("\nField coverage:")
    for field in fields:
        present = sum(
            1
            for record in data
            if record.get(field) not in (None, "", [], {})
        )
        print(f"{field:20} {present}/{len(data)}")

    family_counts = Counter(
        record.get("model_family")
        for record in data
        if record.get("model_family")
    )

    print(f"\nUnique model families: {len(family_counts)}")
    print("\nTop 30 model families:")

    for family, count in family_counts.most_common(30):
        print(f"{family}: {count}")

    provider_counts = Counter(
        len(record.get("providers", []))
        for record in data
    )

    print("\nProvider-count distribution:")
    for count, models in sorted(provider_counts.items()):
        print(f"{count} provider(s): {models} models")


if __name__ == "__main__":
    main()