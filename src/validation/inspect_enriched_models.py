from __future__ import annotations

import json
from pathlib import Path
from collections import Counter
from typing import Any

INPUT = Path(r"F:\AI-Orbit-Models-Pipeline\data\final\models_official_enriched.json")
OUT_JSON = Path(r"F:\AI-Orbit-Models-Pipeline\data\final\enriched_inspection_report.json")


def text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return str(v).strip()


def get_score(r):
    try:
        return int(float(r.get("quality_score", 0)))
    except Exception:
        return 0


def get_identity(r):
    rr = r.get("review_resolution") or {}
    return text(rr.get("resolved_identity_status")) or text((r.get("identity_verification") or {}).get("status"))


def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Input not found: {INPUT}")
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Expected a JSON list")

    rows=[]
    official_domains=Counter()
    enrichment=Counter()
    identity=Counter()
    source_counts=[]

    for r in data:
        oe = r.get("official_enrichment") or {}
        selected = oe.get("selected_official_source") or {}
        status = text(oe.get("status")) or "unknown"
        domain = text(selected.get("domain"))
        if domain:
            official_domains[domain]+=1
        enrichment[status]+=1

        ident=get_identity(r)
        identity[ident]+=1
        inspected=oe.get("inspected_sources") or []
        reachable=sum(1 for s in inspected if s.get("reachable") is True)
        strong=sum(1 for s in inspected if (s.get("identity") or {}).get("status")=="strong_match")
        probable=sum(1 for s in inspected if (s.get("identity") or {}).get("status")=="probable_match")
        urls=[]
        for s in inspected:
            u=text(s.get("final_url") or s.get("url"))
            if u:
                urls.append(u)
        hf=[u for u in urls if "huggingface.co" in u.lower()]
        gh=[u for u in urls if "github.com" in u.lower()]
        row={
            "model_name": text(r.get("model_name")),
            "model_id": text(r.get("model_id")),
            "quality_score": get_score(r),
            "identity_status": ident,
            "enrichment_status": status,
            "official_url": text(selected.get("url")),
            "official_domain": domain,
            "official_source_type": text(selected.get("source_type")),
            "official_identity_score": selected.get("identity_score"),
            "source_count": len(inspected),
            "reachable_sources": reachable,
            "strong_source_matches": strong,
            "probable_source_matches": probable,
            "huggingface_urls": hf,
            "github_urls": gh,
        }
        rows.append(row)
        source_counts.append(len(inspected))

    rows.sort(key=lambda x:(-x["quality_score"], x["model_name"].lower()))
    report={
        "input_records":len(data),
        "enrichment_status":dict(enrichment),
        "identity_status":dict(identity),
        "official_domains":dict(official_domains),
        "rows":rows,
        "summary":{
            "records_with_official_url":sum(bool(x["official_url"]) for x in rows),
            "records_without_official_url":sum(not bool(x["official_url"]) for x in rows),
            "total_inspected_source_entries":sum(source_counts),
            "average_source_entries_per_record": round(sum(source_counts)/len(source_counts),2) if source_counts else 0,
        },
    }
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Records: {len(rows)}")
    print(f"With selected official URL: {report['summary']['records_with_official_url']}")
    print(f"Without selected official URL: {report['summary']['records_without_official_url']}")
    print(f"Average inspected sources/model: {report['summary']['average_source_entries_per_record']}")
    print("\nTOP 41 MODELS:")
    for i,x in enumerate(rows,1):
        print(f"{i:>2}. {x['model_name']} | score={x['quality_score']} | identity={x['identity_status']} | enrichment={x['enrichment_status']} | official={x['official_domain'] or 'none'} | HF={len(x['huggingface_urls'])} | GH={len(x['github_urls'])}")
    print(f"\nDetailed report: {OUT_JSON}")

if __name__ == "__main__":
    main()
