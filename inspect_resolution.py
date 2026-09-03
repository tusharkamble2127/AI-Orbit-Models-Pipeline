import json


PATH = "data/intermediate/entity_resolution_report.json"


def main():
    with open(PATH, "r", encoding="utf-8") as file:
        report = json.load(file)

    comparisons = report.get("comparisons", [])

    strong = [
        item
        for item in comparisons
        if item.get("classification") == "strong_duplicate_candidate"
    ]

    review = [
        item
        for item in comparisons
        if item.get("classification") == "review_required"
    ]

    print("=" * 80)
    print("STRONG DUPLICATE CANDIDATES")
    print("=" * 80)

    for i, item in enumerate(strong, 1):
        print(f"\n[{i}]")
        print("Left :", item.get("left_model_name"))
        print("ID   :", item.get("left_model_id"))
        print("Family:", item.get("left_family"))
        print()
        print("Right:", item.get("right_model_name"))
        print("ID   :", item.get("right_model_id"))
        print("Family:", item.get("right_family"))
        print()
        print("Score:", item.get("score"))
        print("Reasons:", ", ".join(item.get("reasons", [])))
        print("Shared weights:", item.get("shared_weight_urls"))

    print("\n")
    print("=" * 80)
    print("REVIEW REQUIRED")
    print("=" * 80)

    for i, item in enumerate(review, 1):
        print(f"\n[{i}]")
        print(
            item.get("left_model_name"),
            "|",
            item.get("left_model_id"),
        )
        print(
            item.get("right_model_name"),
            "|",
            item.get("right_model_id"),
        )
        print(
            "Family:",
            item.get("left_family"),
            "/",
            item.get("right_family"),
        )
        print(
            "Similarity:",
            item.get("name_similarity"),
        )
        print(
            "Reasons:",
            ", ".join(item.get("reasons", [])),
        )


if __name__ == "__main__":
    main()