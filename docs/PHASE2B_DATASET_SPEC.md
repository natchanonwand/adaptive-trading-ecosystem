# Phase 2B immutable exploratory H1 dataset specification

Phase 2B reconstructs only historical H1 ingestion and evidence. Phase 1 and Phase 2A behavior remains intact. No ticks, indicators, strategy, backtesting, execution, or Phase 3 functionality is introduced.

## Approved source and scope

The only source is the existing `Mt5ReadOnlyProvider`, through its additional strict `get_h1_bars` method. The native SDK remains confined to `discovery/sdk.py`. DEMO status and connectivity remain mandatory; company/server are checked before and after each H1 read. Approved reference: Exness Technologies Ltd / Exness-MT5Trial14. Approved mappings are exactly BTCUSD â†’ BTCUSDm, XAUUSD â†’ XAUUSDm, USTEC100 â†’ USTECm. Alternatives fail closed.

The authorized request is [2021-01-01T00:00:00Z, 2026-09-10T14:00:00Z). Deterministic contiguous UTC chunks contain at most 31 days and are anchored at the requested start; the final chunk is truncated at the exclusive end. The SDK receives end minus one millisecond to implement its inclusive endpoint. Returned rows are retained in source order; no out-of-window rows are silently filtered by the new method.

## Classification and availability

All datasets are `EXPLORATORY_RESEARCH_ONLY`, with `qualification_eligible=false` and `price_basis=MT5_CHART_BAR_BASIS_UNVERIFIED`. Historical chart bars have not been demonstrated to be Bid OHLC. `available_at=close_time` and `availability_basis=MODELED_AT_BAR_CLOSE_FOR_EXPLORATORY_RESEARCH` are modeling conventions, not measurements of historical latency. `close_time=open_time+1 hour`.

## Immutable contracts and authoritative arithmetic

Pydantic frozen contracts reject extra fields. Phase 2B timestamps must be aware and have zero UTC offset; they do not inherit Phase 1's offset-normalizing behavior. H1 opens and requested boundaries must be exactly hour aligned.

OHLC uses PyArrow Decimal128 with **precision 34 and scale 18**: at most 16 integer digits and 18 fractional digits, strictly positive, finite, exactly representable. No rounding is permitted. This matches the existing finite Decimal boundary. SDK double values cross the existing `source_decimal` conversion once through decimal text; their original vendor precision cannot be recovered or established. Binary floats are never authoritative normalized storage. Trailing zero representation may change to fixed scale on readback; the exact numerical value is preserved. Integers for tick volume, spread points, and real volume are nonnegative signed-int64 values.

`Bar` preserves dataset ID, exact mapping, metadata reference and temporal scope, H1 timeframe, open/close/availability/retrieval timestamps, OHLC, tick volume, spread points, real volume, source, optional installed SDK version, price/availability basis, and quality flags. The explicit Arrow schema defines UTC microsecond timestamps, nonnullable fields except source version, and a string-list quality field. PyArrow is locked to 21.0.0; typing stubs are also locked. Schema and arithmetic versions are embedded in Parquet and manifests.

## Evidence and publication

Each asset occupies a new, never-reused directory under Git-ignored `data/datasets/<run>/<asset>/`. It contains allowlisted provider identity, current instrument metadata, a raw JSON observation and receipt for every attempted chunk, quality JSON, normalized Parquet, and a manifest. All writes use exclusive creation. The manifest is written last and is the completion marker. A crash may leave incomplete evidence; existing directories are never overwritten or resumed. Immutability is enforced by application writes and verified hashes, not by a WORM filesystem or external signature.

Raw JSON contains the provider's sanitized observations: Decimal text, integer volumes and UTC times. Malformed source values become explicit null observations and cause validation failure; malformed original native values or arbitrary diagnostics are not persisted. Every returned row remains represented. Each receipt records canonical asset, broker symbol, requested bounds, retrieval time, row count, first/last valid timestamp, status/error, raw file name and SHA-256. Empty successful chunks differ from failed chunks. Read failures remain explicit and prevent publication; they are never silently skipped. Losing DEMO status records the failed attempt and stops further queries immediately.

Current instrument metadata is obtained using the existing Phase 2A snapshot API and hashed. It is always marked `CURRENT_SNAPSHOT_ONLY`; no historical effective date is implied. No previous workstation's ignored snapshot is assumed to have survived recovery.

## Validation and quality

The raw-to-normalized boundary first enforces valid UTC/H1 timestamps, then tests each observation against its requested half-open chunk. An outside observation stays unchanged in raw evidence and is explicitly classified `OUTSIDE_REQUESTED_CHUNK` in quality evidence, with source filename, zero-based raw row index, observed time and requested bounds. It is excluded from normalized candidates before OHLC, duplicate, conflict, ordering or coverage statistics. This is a quarantined provider response, not a repaired bar. `outside_chunk_observation_count` counts these records; `bar_count` counts normalized bars. Raw receipt counts and first/last timestamps continue to describe every returned observation, including quarantined rows. A successful chunk with only quarantined observations has no valid historical coverage and is allowed; its receipt remains `OBSERVED` to describe the raw response.

Normalized validation still rejects naive/non-UTC or unaligned timestamps, invalid close/availability times, malformed or nonpositive Decimal prices, invalid OHLC relationships, invalid volume/spread integers, mapping mismatches, outside-request rows and unexpected ordering. Unknown or unaligned timestamps cannot be excused as quarantine. In-range exact and conflicting duplicates still fail. Provider failures and missing chunks still fail. No silent removals, sorting repairs, forward fills, or synthetic bars can enter a published dataset. Verification recomputes every quarantine record from raw evidence and compares the complete quality result.

Adapter inspection and a regression at `NativeSdk.copy_rates_range` establish that outside timestamps originate in the MetaTrader5 SDK result, not wrapper-generated observations: the native adapter copies fields from each SDK row without time replacement or row synthesis; `get_h1_bars` converts its epoch to UTC and preserves the row. Phase 2A's separate `get_bars` filters its own discovery observations and is unchanged. Why the SDK/terminal returns the first-available bar for pre-history queries is not established here.

Gap measurement uses a derived set of valid open times, without changing authoritative source order. Every missing clock interval, including leading/trailing coverage shortfalls and the entire window of an empty dataset, is `UNCLASSIFIED_GAP`. Each gap records start/end, missing clock hours, previous bar and next bar; an absent boundary neighbor is null. Weekends and holidays receive no automatic interpretation. Quality records counts, validation status, issues, all gaps, missing hours and largest gap. A successful empty retrieval has zero actual coverage and is not useful history, even though its records are structurally valid.

## Identity and verification

The normalized dataset ID is streaming SHA-256 over the existing tagged canonical encoding: a versioned header with requested window and canonical asset, followed by bars in authoritative order. Operational retrieval time, the self-referential dataset ID, metadata snapshot hash and installed source version are excluded. Metadata and source version are provenance, not historical price content. Thus repeated retrievals of the same bars/window have the same normalized ID despite changing retrieval times/current snapshots. Changes to bars, mapping, modeled semantics, window or arithmetic/schema change normalized identity.

The Parquet byte hash is distinct from normalized identity: operational columns and writer provenance can change its bytes. Manifests bind raw source hashes, Parquet and quality hashes, metadata and sanitized provider snapshot hashes, actual/requested coverage, all receipts, counts, classifications, assumptions and unresolved items. A code hash covers the dataset, discovery and domain Python sources, with LF-normalized bytes. Manifest hashing uses sorted compact ASCII JSON excluding only `manifest_hash` itself. Current metadata changes therefore alter the manifest hash even when normalized content is unchanged.

`python -m trading_ecosystem.datasets.verify <root>` validates contracts and hashes, checks schema, reconstructs bars from raw observations, compares them exactly with Parquet, and recomputes quality and coverage. The verifier does not claim external authenticity or qualification. A different code checkout does not invalidate historic evidence automatically; manifests retain the producing code hash.

## Commands and verification gate

Use `scripts/verify_phase2b.ps1` with `uv` on PATH and `TE_TEST_DATABASE_URL` targeting the isolated local PostgreSQL maintenance database. It runs all tests, a fresh migrated database regression, locked dependency sync, Ruff, format check, strict mypy, secret scanning, generated-data ignore checks, synthetic dataset/hash tests, and Git whitespace checks. If real evidence exists, its verification is also required; `-DatasetRoot` selects the evidence root explicitly. With `-RequireRealDatasets` and no explicit root, the newest attempted run must contain all three verified assets; the script never falls back to an older successful run. Older failed runs remain immutable evidence and need not become successful datasets.

Only after the complete code gate passes, run `uv run --locked --extra discovery python -m trading_ecosystem.datasets --ingest`. The CLI fixes the approved research window and all three mappings. Repeat the complete gate afterward with `-RequireRealDatasets -DatasetRoot data/datasets/<successful-run>`; this requires completed verified manifests for all three assets. No commit or tag is automatic.

Secret detection remains enabled with all existing plugins. Synthetic test hashes are constructed from repeated characters; no test detector exclusions are needed. Any inline allowlisting on report digest lines applies only to independently computed SHA-256 artifact identifiers, with a local justification; it does not authorize credentials or account identifiers.

## Unresolved D01/D02

Owner approval resolves the three research mappings and broker reference only. D01 still requires historical contract-unit interpretation/effective dates, valuation and margin reconciliation, commission/financing policy, calendar details, and broker protection/amendment semantics. D02 still requires licensing and retention guarantees, demonstrated Bid basis, observed availability/latency, historical spread/cost schedules and metadata, calendar-aware completeness, qualified quote ordering and evaluation windows. These datasets do not resolve qualification.
