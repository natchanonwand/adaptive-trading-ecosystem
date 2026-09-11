# Phase 2B recovery report

Completed targeted boundary quarantine fix and new read-only H1 ingestion: `20260911T161046Z-ee75c598`.

Baseline remains `056fc21` / `phase2a-v0.1.0`. No commit, tag, Phase 3 work or broker-write capability was introduced.

## Verification

The complete code gate passed before the new ingestion: **171 tests**, including unchanged Phase 1/2A regressions and fresh PostgreSQL migration/regression; Ruff, format, strict mypy, secret scan, ignore checks, retained XAUUSD raw/Parquet/hash verification and Git whitespace checks passed.

The final `scripts/verify_phase2b.ps1 -RequireRealDatasets` passed for this newest run, including independent raw/Parquet/manifest verification of all three assets. The report statistics below come exclusively from this successful run.

## Requested and actual history

Requested interval for every asset: **2021-01-01T00:00:00Z to 2026-09-10T14:00:00Z exclusive**, H1. Source: Exness Technologies Ltd / Exness-MT5Trial14, DEMO gated.

| Asset | Broker symbol | Actual first open UTC | Actual last open UTC | Actual end exclusive UTC | Normalized bars | Raw observations | Outside chunk | Duplicates | Conflicts | Invalid OHLC | Validation |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| BTCUSD | BTCUSDm | 2022-08-01T00:00:00Z | 2026-09-10T13:00:00+00:00 | 2026-09-10T14:00:00Z | 36036 | 36054 | 18 | 0 | 0 | 0 | PASS |
| XAUUSD | XAUUSDm | 2021-01-03T23:00:00Z | 2026-09-10T13:00:00+00:00 | 2026-09-10T14:00:00Z | 33647 | 33647 | 0 | 0 | 0 | 0 | PASS |
| USTEC100 | USTECm | 2022-08-01T00:00:00Z | 2026-09-10T13:00:00+00:00 | 2026-09-10T14:00:00Z | 23977 | 23995 | 18 | 0 | 0 | 0 | PASS |

| Asset | Unclassified gaps | Missing clock hours | Largest gap hours | Failed chunks | Invalid normalized records |
|---|---:|---:|---:|---:|---:|
| BTCUSD | 3 | 13850 | 13848 | 0 | 0 |
| XAUUSD | 1469 | 16239 | 73 | 0 | 0 |
| USTEC100 | 1065 | 25909 | 13848 | 0 | 0 |

All gaps, including leading unavailable requested history, remain `UNCLASSIFIED_GAP`. No session calendar, weekend/holiday classification, filling or synthetic bars were applied. Actual coverage and duplicate statistics use only valid in-range normalized observations.

## Quarantine and source behavior

Every returned provider observation is retained unchanged in raw chunk JSON. Each outside observation has an `OUTSIDE_REQUESTED_CHUNK` quality record linking its source file, zero-based raw row index, observed timestamp and requested half-open interval. `outside_chunk_observation_count` counts these records. Raw receipts still count all returned rows and describe raw first/last timestamps. These are quarantined provider responses, not repaired bars. The verifier reconstructs quarantine and normalized output independently from raw evidence.

Adapter inspection establishes that the outside timestamps originate in the MetaTrader5 SDK response, not generated wrapper logic: `NativeSdk.copy_rates_range` copies each SDK row directly; `get_h1_bars` converts its epoch to UTC without replacing or synthesizing timestamps. A regression verifies that an out-of-range SDK row survives this adapter unchanged. The underlying SDK/terminal reason for returning the first-available bar on pre-history requests is not established.

The failed run `20260911T155007Z-8b7cfe9f` remains untouched. Its full file inventory and SHA-256 values were recorded before this fix and checked afterward. XAUUSD follows the same in-range path, without quarantines. Its previous completed manifest remains readable and verifies unchanged.

## Dataset classification

- `price_basis=MT5_CHART_BAR_BASIS_UNVERIFIED`
- `availability_basis=MODELED_AT_BAR_CLOSE_FOR_EXPLORATORY_RESEARCH`
- `instrument_metadata_temporal_scope=CURRENT_SNAPSHOT_ONLY`
- `qualification_eligible=false`

All three datasets are `EXPLORATORY_RESEARCH_ONLY`. Availability is modeled at bar close, not measured historical latency. Current metadata is not historical contract evidence. Suitability is limited to exploratory inspection of actually supplied bars; these are not qualified Bid OHLC datasets.

## Hashes

### BTCUSD

Evidence: `data/datasets/20260911T161046Z-ee75c598/BTCUSD`; chunks: 68.

- Dataset ID: `1f2a3dfaa770663d7c66c63ea2470e3244ac349c19921501844425dc0ca82e45` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->
- Parquet SHA-256: `3064753708412da9e39907249db29ae1e2de6492feb053cb6fd3b82ef6a2b141` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->
- Manifest SHA-256: `9201bddf8ab402bc83d51331357b9ac88d4a52295691cf37da91c8370105655c` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->
- Metadata SHA-256: `9442ebe8961130f675152e75de04b536e729dd826ac43e462d05539a4193af0a` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->
- Producing code SHA-256: `97011440b7f83eee1a943c21a4f634edb257659c144ab7b64412ac63067ee38d` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->

### XAUUSD

Evidence: `data/datasets/20260911T161046Z-ee75c598/XAUUSD`; chunks: 68.

- Dataset ID: `f2bc196eac87bf1e96ed12e4ddb45d6f62cd3a34a42692acd7ce1e3618afbade` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->
- Parquet SHA-256: `670df351fb05bb41b622cd8f1c8e568db188d6c60ce961ec47204bd93966f89d` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->
- Manifest SHA-256: `6de42614efa8fca715ffbac7bced898659cdc9d16b97eeddb7dc72e8dda9b34d` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->
- Metadata SHA-256: `6784cc5714bea9e5600b9d052c653fa9bc101e48f86fbcc4e047c8616fa622d2` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->
- Producing code SHA-256: `97011440b7f83eee1a943c21a4f634edb257659c144ab7b64412ac63067ee38d` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->

### USTEC100

Evidence: `data/datasets/20260911T161046Z-ee75c598/USTEC100`; chunks: 68.

- Dataset ID: `0971cf0a3ea426958406a22effcfb09c3d4bdb3e8c388715605c872747f653d0` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->
- Parquet SHA-256: `8a4e27e69f68a196e4259c1e10ee6bc86ef56b7a519aa2d4e4e7710a7e9347d3` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->
- Manifest SHA-256: `c83a71711983445efbb02e4d3df52ec86d5f4a150854274eab7ccc9910703e22` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->
- Metadata SHA-256: `693a3dcdf530211de931c36f5e0e02bd8a35c294dd576186ace8aa034ae30b60` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->
- Producing code SHA-256: `97011440b7f83eee1a943c21a4f634edb257659c144ab7b64412ac63067ee38d` <!-- pragma: allowlist secret -- verified non-secret artifact SHA-256 -->

## Files and scope

Targeted changes: dataset contracts, normalization/ingestion, quality assessment, evidence verification, dataset regression tests, `scripts/verify_phase2b.ps1`, `docs/PHASE2B_DATASET_SPEC.md` and this report. The Phase 2A adapter, safety boundaries, approved mappings, Decimal128(34,18) Parquet schema, normalized identity algorithm and XAUUSD in-range behavior are unchanged by this fix. Quality adds backward-compatible quarantine fields, cryptographically bound through the existing manifest quality hash.

The normalized range validator still rejects out-of-window candidates. In-range exact/conflicting duplicates, malformed records, invalid OHLC, timestamp violations, provider errors and missing chunks still fail. No existing strict range test was relaxed; the former ingestion test for an outside-only response was replaced with explicit quarantine tests under the newly authorized policy.

## Unresolved D01/D02

D01: mappings and the broker reference are approved for research/demo only. Historical contract units/effective dates, valuation/margin reconciliation, commission/financing policy, calendars and protection/amendment semantics remain unresolved.

D02: licensing/retention guarantees, proof of Bid price basis, observed latency, historical spread/cost schedules and metadata, calendar-aware completeness, qualified quote ordering and evaluation windows remain unresolved. Quarantine does not resolve these qualification limitations.
