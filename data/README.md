Generated data lives here and is not committed. Layout:

- `cache/` HTTP response cache
- `raw/` bronze layer: source payloads as downloaded, never modified
- `processed/` silver layer: normalised Parquet tables
- `features/` gold layer: model-ready Parquet tables
- `manifests/` provenance registry, coverage reports, entity-mapping reports
- `models/` versioned model artifacts and metadata
