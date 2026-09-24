# PHASE 4C — BEHAVIORAL DATASET & FEATURE ENGINE

FEATURE ENGINE IMPLEMENTATION: COMPLETE / PASS.
REAL EA FEATURE QUALIFICATION: NOT PROVIDED.
Data type: SYNTHETIC_QUALIFICATION. No real external EA performance conclusions.

Phase 4B was reviewed, secret/scope/export checks passed, and the authorized local
checkpoint was created as `6ada091` (`feat: add deterministic external EA observer`).
No tag or push. Phase 4C remains uncommitted and stops before Phase 4D.

## Phase 4B benchmark sanity

The old 32.73-second stress figure included Python memory tracing and excluded
export time. It is not a measurement of normal uninstrumented polling alone.
The new benchmark instruments the unchanged observer from an external harness;
no production observer methods, sizing or calibration formulas were changed.

| Processing metric (ms) | 1 EA / 3 symbols | 3 EA / 12 positions | Same stress with tracemalloc |
| --- | ---: | ---: | ---: |
| Polls | 60 | 12 | 12 |
| Min | 2.072 | 254.331 | 1,555.790 |
| Median | 3.216 | 329.147 | 2,271.799 |
| p95 | 182.077 | 463.115 | 2,811.166 |
| Max | 213.184 | 489.048 | 2,982.335 |
| Requested interval | 1,000 | 1,000 | 1,000 |
| Processing budget misses | 0 | 0 | 12 |
| DB commit median, summed per poll | 0.880 | 1.344 | 1.490 |
| DB commit p95, summed per poll | 2.192 | 1.683 | 2.582 |
| SQL statement median, summed per poll | 1.350 | 46.706 | 112.993 |
| SQL statement p95, summed per poll | 30.753 | 65.893 | 134.134 |

| Timing component (seconds unless specified) | Normal | Stress | Stress traced |
| --- | ---: | ---: | ---: |
| Fixture mutation total, ms | 16.112 | 0.782 | 2.979 |
| Scheduled sleep | 57.057613 | none | none |
| Loop wall time | 60.124309 | 4.120102 | 26.831687 |
| Setup | 0.322594 | 0.101694 | 0.106075 |
| Stop/teardown measurement | 0.002925 | 0.002634 | 0.001854 |
| Export | 0.535880 | 0.824083 | 0.757034 |
| Total wall time | 60.986487 | 5.049285 | 27.698342 |
| Loop CPU | 2.578125 | 3.890625 | 25.984375 |
| Traced Python peak bytes | not measured | not measured | 1,436,340 |
| Net behavior event additions | 27 | 192 | 192 |

The normal case has 0–3 net new events per poll. Stress has 60 initial facts then
12 stop-change events per remaining poll (192 total). Per-poll arrays, all commit
statistics and exact unrounded timings are retained in `.local/phase4_c/polling.json`
and the three `polling-*/timing.json` files. Event-count queries are outside the
processing timer but inside loop/total wall time. SQL timings are cursor execution
durations; commit timing wraps actual dialect commit calls. They do not attribute
all serialization, replay, connection or Python work to the database. p95 uses
the nearest index at `(n-1)*0.95`; these small samples are descriptive only.

`missed_deadline_count` means processing exceeded the requested 1,000 ms budget,
not an end-to-end fixed scheduler SLA. Stress deliberately runs without sleeps.
The untraced bounded workload stayed within that processing budget; tracing did
not. The known limitation remains: traced/stress/long sessions and native history
reads can overrun one-second cadence. No production throughput guarantee or silent
optimization is claimed. Features are downstream and never run inside observer step.

## Implementation qualification

| Requirement | Result | Evidence/semantics |
| --- | --- | --- |
| Feature registry | PASS | 100 explicit definitions with version, source, dtype and availability |
| Temporal features | PASS | Configurable fixed UTC windows, overlap/cross-midnight tests |
| Price/distance | PASS | Directional valid SL/TP, nullable distances and observed reward/risk |
| ATR | PASS | Wilder14, 15-bar minimum, five timeframes |
| EMA | PASS | H1 20/50/200 SMA seeds; insufficient history stays null |
| RSI | PASS | Wilder14 M15/H1; deterministic known gain/loss fixtures |
| ADX | DEFERRED | Explicitly allowed; no ambiguous smoothing implementation |
| Volatility | PASS | ATR, population return std, closed-bar ranges and normalizations |
| Market structure measurements | PASS | Numeric N=20 distances/range position/most-recent extrema |
| Sequence features | PASS | Known candidate/symbol prior events only |
| Episode behavior | PASS | Scale-in, partial fractions, sequences and first-observed stop delays |
| Account context | PASS | Eligible snapshot no later than broker entry; nominal exposure only |
| Closed-bar alignment | PASS | Exact close/one-second-before boundaries and 10:37:15 M15 fixture |
| Multi-timeframe alignment | PASS | M1/M5/M15/M30/H1/H4 independently aligned |
| Leakage firewall | PASS | Availability bounds, strict X schema, Y excluded |
| Adversarial leakage tests | PASS | Future candle/exit/later SL/later equity cannot affect initial X |
| Entry/outcome separation | PASS | Distinct X episode/entry tables and Y table |
| Missing-data semantics | PASS | Null reasons, no implicit zero fill, finite-type checks |
| Quality metadata | PASS | Confidence, recovery, history sufficiency/gaps, entry-time basis |
| Deterministic rebuild | PASS | Two builds/exports per normal and stress source |
| Canonical content hashes | PASS | Source, schema, content/file hashes and reopened rows |
| Replay compatibility | PASS | Materialized Phase 4B versus independent raw replay agree |
| Time-aware splits | PASS | Chronological locked OOS; crossing causal groups purged |
| Statistics/correlation utilities | PASS | Descriptive only; ties/null/constant/small-sample cases |
| Offline/read-only boundary | PASS | No native attachment; CLI consumes recorded files |
| Feature Data dashboard | PASS | Desktop/mobile review, synthetic label, missingness and quality |
| Targeted Phase 4C tests | 45 PASS | 37 unit/property cases + 8 PostgreSQL integration cases |
| Python/PostgreSQL full suite | 962 PASS | Includes 142 PostgreSQL integration cases; zero failures, errors or skips |
| Frontend tests/quality | 69 PASS | Typecheck, lint, format and production build passed |
| Ruff / format / strict mypy | PASS | Repository-wide checks; 243 formatted files, 205 typed files |
| Secret scan | PASS | 309 project files; no findings, including final report scan |
| Phase 2B–4B regressions | PASS | Full composed chain; 12 retained research results verified without rerunning simulations |
| Frozen evidence 874 | UNCHANGED | Final byte-for-byte hash comparison passed |
| Phase 4B evidence | 53 files UNCHANGED | Final preserved-evidence comparison passed |

The full `scripts/verify_phase4_c.ps1` gate completed on 2026-09-24 with exit
code 0. `test-results/phase4_c.xml` records 962 tests, including 142 PostgreSQL
integration cases, with zero failures, errors or skips. The composed historical
verifiers run the same full suite twice; 962 is the unique suite count, not a sum
of repeated runs. The 45 targeted Phase 4C tests are included in that total.
Frontend evidence is `test-results/phase3_6-frontend.xml` (69 tests).
The unchanged historical Phase 3.3B verifier emitted a non-failing Pydantic
`model_fields` deprecation warning; its evidence checks completed successfully.

## Datasets and build benchmark

Feature set: `behavioral-v1-fa9837ad8f0229e7936db2b3`.
Schema: BEHAVIORAL_FEATURES_V1. Builder: 4C_V1_DECIMAL34.
Feature count: **100 = 74 causal + 26 outcome fields**. Metadata columns are extra.
`built_at` is a labeled deterministic source-observation cutoff, not wall time.

| Dataset | Normal rows / columns | Stress rows / columns |
| --- | ---: | ---: |
| episode_features | 2 / 86 | 12 / 86 |
| entry_features | 3 / 86 | 12 / 86 |
| episode_outcomes | 2 / 31 | 12 / 31 |

| Build measurement | Normal | Stress |
| --- | ---: | ---: |
| Input episodes | 2 | 12 |
| Market-context/window rows | 72 | 54 |
| Build seconds including source verification, with memory tracing | 2.205244 | 4.102617 |
| Traced Python peak bytes | 3,668,231 | 2,426,594 |

Build timings exclude subsequent export/repeated validation. Memory is traced
Python allocation peak, not process/MT5/PostgreSQL RSS. These fixtures validate
correctness and detect gross cost; they are not evidence of predictive quality.

Evidence is under `.local/phase4_c/features-final-v2/`: `normal`, `normal-repeat`,
`stress`, `stress-repeat` and `qualification.json`. Each manifest contains exact
source manifest SHA-256, config/source-code identities, table SHA-256 and canonical
content hashes. Repeated exports are byte-identical with pinned PyArrow 21.0.0;
the required portable guarantee is canonical logical identity.

Normal source session: `5978615e-717f-48f2-90f2-adab44fe4435`.
Stress source session: `57284d81-1dd2-4346-8b17-1f12011b5467`.
The original `.local/phase4_b/final/` exports are read-only inputs.

## Limitations, decisions and deviations

- REAL EXTERNAL EA DATA: NOT PROVIDED. All generated qualification data is synthetic.
- No conclusions about profitable patterns, EA edge, best indicators or correlations.
- Final review added a preexisting-episode scale-in regression: later increases
  cannot become the original episode entry. It also added a known matching-currency
  guard for nominal equity ratios. Interim artifacts in `features-final/` remain
  preserved; the accepted set has a new source-derived identity and `features-final-v2/`
  namespace. The preliminary full gate was interrupted for these bounded fixes;
  the final full gate passed from the completed state.
- ADX is deferred as authorized. Initial market-structure features use N=20 to keep
  the catalog disciplined; there is no combinatorial parameter search.
- Sessions are explicit fixed UTC analytical windows, not London/New York civil
  sessions. DST/holiday exchange calendars are deferred; no fixed civil UTC offset
  is silently assumed.
- Source contexts contain 50 bars, so EMA200 is null for all current qualification
  rows. Unit fixtures separately prove sufficient-history EMA200 calculation.
- Delayed broker deal discovery can leave contemporaneous quotes unavailable;
  normal entry spread fields are null for both episode rows. No later quote is used.
- Partial/recovered/mixed episodes have unknown financial/holding outcomes where
  opening/closing evidence is insufficient. Unknown values are not performance zeroes.
- Exact Decimal values use wide string columns with logical-type metadata; consumers
  must parse Decimal explicitly. No uncontrolled binary float conversion.
- Chronological splitting conservatively co-groups candidate/symbol sequences and
  uses source-end availability; boundary groups may be purged rather than fragmented.
- Strong dataset validation requires the recorded source exports and matching feature
  package identity to remain available. Old sets are not interpreted under new code.
- The first integration check exposed Parquet list child naming (`item` vs `element`);
  the schema was corrected while retaining strict schema/hash/readback checks.
- New numeric/time test assertions were corrected to compare Decimal/UTC values,
  not incidental trailing-zero or Z/+00:00 formatting. No frozen tests were weakened.
- Dashboard navigation assertions now include the eighth page and keep prior Risk
  and Observer safety assertions. No observer, risk/accounting or calibration code changed.

## Files added and modified

Added project files:

- `PHASE4_C_REPORT.md`
- `docs/PHASE4_C_BEHAVIORAL_FEATURE_ENGINE.md`
- `reports/feature_registry.json`
- `dashboard/src/FeaturePage.tsx`
- `dashboard/tests/features.test.tsx`
- `scripts/qualify_phase4_c_polling.py`
- `scripts/qualify_phase4_c.py`
- `scripts/verify_phase4_c.ps1`
- `scripts/verify_phase4_c_evidence.py`
- `src/trading_ecosystem/features/__init__.py`
- `src/trading_ecosystem/features/__main__.py`
- `src/trading_ecosystem/features/api.py`
- `src/trading_ecosystem/features/builder.py`
- `src/trading_ecosystem/features/contracts.py`
- `src/trading_ecosystem/features/dataset.py`
- `src/trading_ecosystem/features/families.py`
- `src/trading_ecosystem/features/indicators.py`
- `src/trading_ecosystem/features/outcomes.py`
- `src/trading_ecosystem/features/registry.py`
- `src/trading_ecosystem/features/splits.py`
- `src/trading_ecosystem/features/statistics.py`
- `src/trading_ecosystem/features/temporal.py`
- `tests/features/__init__.py`
- `tests/features/fixtures.py`
- `tests/features/test_causality.py`
- `tests/features/test_episodes.py`
- `tests/features/test_indicators.py`
- `tests/features/test_scope.py`
- `tests/features/test_statistics_split.py`
- `tests/integration/test_feature_dataset.py`

Modified: `dashboard/src/App.tsx` (offline page integration) and
`dashboard/tests/components.test.tsx` (exact navigation and preserved safety checks).
No previous verifier files or observer package files were modified.

Generated local evidence is Git-ignored under `.local/phase4_c/` and `test-results/`.
Browser review: `test-results/phase4_c-browser.json` plus desktop/mobile screenshots;
both sizes have no page overflow or JavaScript exceptions. Full-gate log:
`test-results/phase4_c-complete-gate.log`.

Stop for review before Phase 4D. No Phase 4C commit, tag, push, training, inference,
behavior classification, parameter optimization, copy trading or execution.
