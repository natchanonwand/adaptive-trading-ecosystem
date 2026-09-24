# Phase 4C — Behavioral Dataset & Feature Engine

This offline module converts verified Phase 4B Parquet evidence into numerical
measurements. It does not attach to MT5, change the observer, train models, infer
EA behavior, rank strategies, optimize parameters or execute trades. The local
Phase 4B checkpoint is `6ada091`. Real external EA data was not provided.

## Architecture and lineage

`features.builder` reads the immutable Phase 4B manifest, verifies all four source
datasets using the existing observer verifier, and indexes context/window hashes.
It builds from materialized events/episodes and independently from raw-frame
replay. Export requires exact agreement. Neither path writes to the source.

Families are separated into temporal/calendar, closed-bar indicators and ranges,
causal context/sequence measurements, and post-entry episode outcomes. Statistics,
chronological splitting, dataset validation, CLI and the read-only quality API
are downstream utilities. No feature computation is imported into the observer
polling path. No dependency or frozen accounting/risk/calibration formula changes.

The initial catalog contains exactly 100 fields: 74 causal measurements and
26 outcome/episode fields. All twelve requested families are represented. The
machine-readable `reports/feature_registry.json` is generated from `registry.py`;
each definition specifies name, version, family, dtype, source, lookback,
timeframe, definition, availability, nullable status and causal status.

Feature-set identity combines the catalog and a SHA-256 fingerprint of the feature
package source (normalized line endings). Changing implementation or definitions
changes the identity even if a developer forgets to update the human version.
Manifest fields include schema version, builder version/source hash, feature-set
ID, source manifest hashes, source session/observer versions, build configuration
and its hash. Reader validation rejects mismatched current code or definitions.
Older feature sets require their matching source checkpoint; they are never
silently reinterpreted by a newer builder.

## Time and leakage rules

Rows use the entry event's **first observed timestamp** as `prediction_cutoff`.
This is an observation-time dataset, not a claim of access before broker execution.
Every populated X cell has a recorded availability upper bound at or before that
cutoff. Null cells have null availability and a documented missing reason.

Stricter rules apply to entry context:

- Bars must close at or before broker entry time when known, otherwise the recovered
  first-observed cutoff. Each timeframe aligns independently; future/incomplete
  bars are filtered out. No nearest-bar forward match or future forward-fill.
- Snapshot/account/instrument state must have been observed at or before broker
  entry and no more than five seconds earlier. A delayed history discovery poll
  cannot supply its later stops, position state, equity or metadata as entry state.
- Quotes must be from the referenced entry context and not later than entry.
  Historical spread comparisons use distinct timestamped observed quotes available
  by the observation cutoff and broker entry cutoff, never backtest spread models.
- Prior-sequence features use only known external candidate/symbol observations
  whose broker times are strictly earlier and whose observed times are no later
  than the current cutoff. Same-time ordering is not promoted into causal proof.
- Future exit fields, full-episode financial results, holding duration, stop-change
  counts/delays and final episode confidence exist only in Y.

Quality includes entry observation/source confidence, whether entry time is known,
context completeness, six timeframe history counts/sufficiency flags, observed
bar gaps, recovered state, ambiguous attribution and per-feature missing reasons.
Context completeness means all six retained windows meet the observer's requested
count; it does **not** imply sufficient history for every indicator. For example,
the 50-bar qualification context cannot produce EMA200. Sufficiency flags use
the longest registered lookback for that timeframe. Gaps are flagged; indicators
use retained closed bars, not fabricated gap fills.

The leakage tests inject a future candle, future exit price/P&L, later SL changes
and later account equity; initial X rows must remain unchanged. Additional tests
reject future availability, Y-column injection, infinities, invalid dtypes,
undocumented nulls, duplicate row IDs, and metadata/provenance tampering.

## Numeric and indicator definitions

All calculations use the repository Decimal34 / half-even context. Financial
quantities never pass through binary floats. Indicator outputs use the same
Decimal arithmetic. Time durations originate from datetime differences; conversion
uses the string representation of seconds. Performance measurements alone use
floating wall/CPU timers and are not feature values.

- EMA20/50/200: SMA of the first N retained closes, then alpha=2/(N+1). Fewer than
  N closes means null. These are explicitly finite-context EMAs, not infinite-history
  broker indicators. H1 values, ATR-normalized price distances and EMA differences
  are included.
- ATR14: true range is max(high-low, abs(high-prev_close), abs(low-prev_close)).
  Seed with the mean of the first 14 true ranges, requiring 15 bars. Continue
  Wilder smoothing `(13*previous+TR)/14`. M5/M15/M30/H1/H4 are included.
- RSI14: Wilder-smoothed positive/negative close differences, seeded by their
  first 14-value means. Zero loss with positive gain gives 100; both zero gives
  50. M15 and H1 are included.
- ADX/+DI/-DI: deliberately deferred. No ambiguous or untested smoothing variant.
- Returns: simple close[t]/close[t-lag]-1, lag 1 across six timeframes; M15 also
  lags 3/5/10. M15 return_std_20 is population standard deviation of 20 returns,
  requiring 21 closes. Decimal square root is used.
- M15 ranges 10/20: maximum high minus minimum low. Structure uses N=20 numeric
  distances, position within range and bars since the most recent tied high/low.
  Flat ranges produce null normalized position, not division by zero. Range
  position can be outside [0,1]; no clipping or categorical interpretation.
- M15 stop/TP/spread/bar-range normalizations divide only by positive ATR.
- Quantiles use linear interpolation at `(n-1)*p` (Type 7); descriptive standard
  deviation uses population denominator n. Missing values are excluded and counted.

SL/TP distances are directional: valid SL must lie on the loss side and TP on the
profit side. Reward/risk requires both positive distances. A missing/invalid stop
does not become zero. `initial_*` means the eligible first observed entry-time
state, not an invented original broker stop instruction. Notional is price * lots
* contract size; notional/equity is a nominal exposure ratio, **not validated risk**.
The ratio also requires a known matching instrument profit currency and account
currency; otherwise it is null and currency quality metadata records the reason.
No risk_percent is emitted while broker economics remain PARTIAL.

## Analytical units and outcomes

- `episode_features`: one row per broker-position episode's first confirmed entry,
  or a clearly recovered first-state anchor when entry is unknown.
- `entry_features`: one row per confirmed opening/increase fill. Recovered states
  do not invent an entry row. This table's granularity is not mixed into episode X.
- A later confirmed scale-in on preexisting exposure gets its own entry row but
  cannot replace the original recovered/unknown episode-entry anchor in episode X.
- `episode_outcomes`: one row per episode, keyed separately. Financial totals are
  populated only for complete, confirmed closed, nonambiguous episodes. Unknown
  opening time means null holding/partial-close delay. Mixed reversals stay partial.

Entry and volume sequences remain list columns in Y. Scalar sequence summaries
include entry count, maximum successive volume ratio, median entry spacing in time
and absolute price. First partial fraction uses exposure immediately before that
partial; cumulative partial fraction uses total confirmed entered volume and is
null for unresolved/reversal sequences. Stop-change delays are explicitly
first-observed delays, not exact broker modification times.

Unknown attribution remains visible with quality flags and null candidate/sequence
identity; it is not assigned to a known EA by magic heuristics. Descriptive dataset
statistics cover the rows supplied and are not EA-specific performance claims.

## Schema, validation and deterministic export

Wide Parquet columns carry typed integers/booleans/strings/list values. Exact Decimal
values are encoded as strings with `logical_type=decimal` field metadata, matching
repository numeric conventions and avoiding fixed-scale rounding. Consumers must
parse those columns explicitly as Decimal. Availability/quality are canonical JSON
metadata columns, separate from the numerical X fields. Export rejects unexpected
columns, invalid finite numeric values and duplicate analytical primary keys.

Each table manifest records name, schema/version identities, session IDs, rows,
columns, config hash, file SHA-256 and canonical content hash. `built_at` and
`created_at` are deterministic logical build cutoffs: the latest immutable source
observation, explicitly labeled `LATEST_IMMUTABLE_SOURCE_OBSERVATION`; they are not
wall-clock export timestamps. Measured build duration is separate qualification
metadata. Repeated builds must have identical logical rows/order/content; pinned
PyArrow qualification also compares byte-identical exports. No cross-writer byte
identity is promised. Existing output directories are refused.

Validation reopens Parquet, checks full Arrow schema and hashes, independently
rebuilds from raw observations, and compares rows, metadata and summaries. Source
exports must remain accessible for this strong validation. Path entries are local
lineage references; move/rebase requires an explicitly new export, not silent edits.

## Splitting and statistics

`features.splits.split` creates chronological train/validation/locked_oos assignments
using exclusive upper bounds. It never shuffles. Episode mode also co-groups the
entire candidate/symbol causal sequence within a session; session mode co-groups
the whole session. Groups whose observed span crosses a boundary are purged.
Outcome availability is conservatively bounded by the source session's final
observation, so this may purge more data than a finer validated interval model.
That conservative choice prevents fragments/outcomes leaking across partitions.
Locked OOS is an explicit immutable assignment contract, not a model-access service.

Descriptive utilities report count, missing count, mean, median, population std,
min, p25/p75/p95/max and categorical counts/proportions. Pearson and Spearman are
pairwise complete; Spearman uses average tied ranks, fewer than three pairs gives
INSUFFICIENT_SAMPLE, and constant columns give CONSTANT_COLUMN. No fake-data
correlation, profit, indicator ranking or predictive conclusion is drawn.

## Offline commands and dashboard

```powershell
.venv\Scripts\python.exe -m trading_ecosystem.features build `
  --source .local/phase4_b/final/normal-export --output .local/phase4_c/new-build
.venv\Scripts\python.exe -m trading_ecosystem.features validate .local/phase4_c/new-build
.venv\Scripts\python.exe -m trading_ecosystem.features summarize .local/phase4_c/new-build
.venv\Scripts\python.exe -m trading_ecosystem.features registry --output reports/feature_registry.json
```

`export` is an alias for the complete build/export pipeline. Repeated `--source`
inputs are deduplicated by session and manifest identity; conflicting exports of
the same session fail. Optional `--config` supplies explicit build/session windows.
Default sessions are UTC_00_08, UTC_08_16 and UTC_16_00, fixed UTC analytical windows.
They do not claim London/New York opening calendars and do not apply DST. Cross-
midnight and overlapping windows are deterministic; overlap delay is null. Civil
exchange-session/DST holiday calendars are deferred rather than silently approximated.

The Feature Data page shows provenance, versions, row/column counts, causal/outcome
counts, missingness and source confidence. It makes no behavior verdict. Its optional
standalone reader is loopback GET-only:

```powershell
.venv\Scripts\python.exe -m trading_ecosystem.features serve .local/phase4_c/new-build
```

It binds port 8765 and requires no MT5/database. Run it when that port is free; the
existing dashboard proxy serves `/api/v1/features`. Other broker/telemetry routes
are intentionally unavailable in this offline reader. The Feature Data page hides
unrelated telemetry controls/status and shows its own offline dataset status;
other monitoring pages still report their telemetry connection truthfully.
There is no automatic fallback to mock data. Changing the selected local dataset
requires restarting the reader; it does not watch or mutate evidence.

## Qualification, limitations and stop

Qualification uses preserved Phase 4B normal/stress fake exports, under the new
`.local/phase4_c/` namespace. The manifest explicitly says SYNTHETIC_QUALIFICATION;
fake registry evidence cannot be relabeled REAL_DEMO_OBSERVATION. Real qualification
remains NOT PROVIDED. Phase 4B polling is separately instrumented by a benchmark
harness; production observer code is unchanged. Memory tracing overhead and
processing-budget misses are reported separately from untraced timings.

Run `scripts/verify_phase4_c.ps1` for targeted tests and the unchanged composed
Phase 2B–4B gate, followed by feature/source evidence verification. Frozen 874 files
and all captured Phase 4B files are compared against the pre-Phase 4C baseline.
No historical simulations are regenerated. Stop after implementation review:
no Phase 4C commit, tag, push, Phase 4D analysis, model training or execution.
