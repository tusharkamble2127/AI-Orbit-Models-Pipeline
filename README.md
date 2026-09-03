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

The pipeline processes AI model data through a structured sequence of discovery, verification, curation, enrichment, and validation stages.

                         ┌──────────────────────────────┐
                         │         Data Sources         │
                         │ Models.dev • OpenRouter      │
                         │ Hugging Face • Official Docs │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │      Discovery & Extraction  │
                         │  model discovery • metadata  │
                         │      provider information    │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │     Normalization Layer      │
                         │ standardization • schema     │
                         │      normalization            │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │   Entity Resolution Layer    │
                         │ duplicate detection • model  │
                         │      identity matching        │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │   Verification & Validation  │
                         │ source verification •        │
                         │ identity verification        │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │       Quality & Curation     │
                         │ 100-point scoring • filtering │
                         │     • candidate selection    │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │      Enrichment Layer        │
                         │ official metadata • pricing  │
                         │ license • benchmarks • links │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │   Canonical Dataset Layer    │
                         │ variant resolution • schema   │
                         │       normalization          │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │      Final Validation        │
                         │ duplicates • URLs • fields   │
                         │ descriptions • quality score │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │      CSV / JSON Export       │
                         │   models_final.csv           │
                         │   models_final_public.json   │
                         └──────────────────────────────┘
