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
Discovery
    |
    v
Extraction
    |
    v
Normalization
    |
    v
Entity Resolution
    |
    v
Source Verification
    |
    v
Identity Verification
    |
    v
Quality Scoring
    |
    v
Curation
    |
    v
Official Enrichment
    |
    v
Variant Resolution
    |
    v
Canonical Dataset
    |
    v
Schema Normalization
    |
    v
Targeted Enrichment
    |
    v
Field Applicability
    |
    v
Final Evidence Enrichment
    |
    v
Description Generation
    |
    v
Final Validation
    |
    v
CSV / JSON Export