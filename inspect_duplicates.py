import json
from collections import defaultdict


PATH = "data/intermediate/models_dev_normalized.json"


def normalize(value: str | None) -> str:
    if not value:
        return ""

    return (
        value.lower()
        .replace("-", " ")
        .replace("_", " ")
        .replace("/", " ")
        .replace(".", " ")
        .strip()
    )


def main() -> None:
    with open(PATH, "r", encoding="utf-8") as file:
        records = json.load(file)

    # ---------------------------------------------------------
    # 1. Exact duplicate model IDs
    # ---------------------------------------------------------
    id_groups = defaultdict(list)

    for record in records:
        model_id = record.get("model_id")

        if model_id:
            id_groups[model_id].append(record)

    exact_id_duplicates = {
        key: value
        for key, value in id_groups.items()
        if len(value) > 1
    }

    print("=" * 70)
    print("EXACT MODEL ID DUPLICATES")
    print("=" * 70)
    print("Groups:", len(exact_id_duplicates))

    for key, value in list(exact_id_duplicates.items())[:20]:
        print(f"{key} -> {len(value)} records")

    # ---------------------------------------------------------
    # 2. Normalized-name collisions
    # ---------------------------------------------------------
    name_groups = defaultdict(list)

    for record in records:
        name = normalize(record.get("model_name"))

        if name:
            name_groups[name].append(record)

    name_collisions = {
        key: value
        for key, value in name_groups.items()
        if len(value) > 1
    }

    print()
    print("=" * 70)
    print("NORMALIZED NAME COLLISIONS")
    print("=" * 70)
    print("Groups:", len(name_collisions))

    for key, value in list(name_collisions.items())[:30]:
        print()
        print("Normalized name:", key)

        for record in value:
            print(
                "  -",
                record.get("model_name"),
                "|",
                record.get("model_id"),
                "| family:",
                record.get("model_family"),
            )

    # ---------------------------------------------------------
    # 3. Family + normalized name candidates
    # ---------------------------------------------------------
    family_name_groups = defaultdict(list)

    for record in records:
        family = normalize(record.get("model_family"))
        name = normalize(record.get("model_name"))

        if family and name:
            family_name_groups[(family, name)].append(record)

    family_name_collisions = {
        key: value
        for key, value in family_name_groups.items()
        if len(value) > 1
    }

    print()
    print("=" * 70)
    print("FAMILY + NAME COLLISIONS")
    print("=" * 70)
    print("Groups:", len(family_name_collisions))

    for (family, name), value in list(
        family_name_collisions.items()
    )[:30]:
        print()
        print("Family:", family)
        print("Name:", name)

        for record in value:
            print(
                "  -",
                record.get("model_name"),
                "|",
                record.get("model_id"),
            )


if __name__ == "__main__":
    main()