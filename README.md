# AIOrbit Models Data Pipeline

A modular data curation and enrichment pipeline for discovering, verifying,
deduplicating, scoring, enriching, validating, and exporting AI model records.

## Project Overview

This project builds a structured dataset of relevant AI models using multiple
discovery and verification stages.

The pipeline focuses on:

- model discovery
- extraction and normalization
- entity resolution and variant detection
- source and identity verification
- model quality scoring
- official-source enrichment
- field-level enrichment
- description generation
- final validation
- CSV and JSON export

## Current Dataset

The current curated candidate dataset contains:

- 41 model records
- 31 public-facing columns
- 0 duplicate model IDs
- 100% description coverage
- 100% source URL coverage
- 100% quality score coverage
- 100% benchmark coverage
- 100% official website coverage
- 100% final CSV schema validation

Some fields are intentionally not complete for every model because they are
model/provider dependent or not publicly available.

Examples include:

- software license for proprietary/API models
- Hugging Face availability for proprietary models
- public download metrics
- model-specific pricing
- embedding support

Missing information is not fabricated.

## Pipeline Architecture

The pipeline follows a multi-stage process from model discovery to final public dataset export:

**1. Discovery**  
→ Model discovery from Models.dev and related sources

**2. Extraction**  
→ Extract raw model metadata and provider information

**3. Normalization**  
→ Convert heterogeneous source data into a consistent structure

**4. Entity Resolution**  
→ Identify duplicate, similar, and potentially related model identities

**5. Source Verification**  
→ Verify model pages, provider sources, and supporting references

**6. Identity Verification**  
→ Confirm that each candidate corresponds to a distinct real-world model

**7. Quality Scoring**  
→ Score models using capability, usefulness, adoption, benchmarks, activity, technical quality, accessibility, and differentiation

**8. Curation**  
→ Select high-quality and relevant model candidates

**9. Official Enrichment**  
→ Add official websites and provider-level metadata

**10. Variant Resolution**  
→ Review model versions, aliases, and variants conservatively

**11. Canonical Dataset**  
→ Produce one canonical record per selected model identity

**12. Schema Normalization**  
→ Map records into the final 31-field public schema

**13. Targeted Enrichment**  
→ Fill provider-specific metadata gaps

**14. Field Applicability**  
→ Determine whether missing fields are applicable, unavailable, or not publicly disclosed

**15. Final Evidence Enrichment**  
→ Add verified supporting evidence for remaining fields

**16. Description Generation**  
→ Generate standardized model descriptions from available evidence

**17. Final Validation**  
→ Validate records, URLs, descriptions, quality scores, schema, and duplicate IDs

**18. CSV / JSON Export**  
→ Export the final public dataset in CSV and JSON formats
