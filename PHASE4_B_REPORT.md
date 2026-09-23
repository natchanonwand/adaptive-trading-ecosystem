# PHASE 4B — EXTERNAL EA OBSERVER

PHASE 4B IMPLEMENTATION: COMPLETE / PASS.
REAL EXTERNAL EA QUALIFICATION: NOT PROVIDED.
REAL_EXTERNAL_EA_SMOKE = BLOCKED / NOT PROVIDED.
No Phase 4B commit, tag, push, Phase 4C, execution or EA activation.
Preserved Phase 4A.1 checkpoint: `5f25848`.

## Qualification

| Requirement | Result | Evidence |
| --- | --- | --- |
| Raw observation capture | PASS | PostgreSQL immutable frames, raw hashes and corruption rejection |
| Lifecycle reconstruction | PASS | BUY/SELL fills, scale-in, partial close and overlap dedup |
| Preexisting recovery | PASS | Unknown entry time and duration remain null; confirmed exit retained |
| Partial close | PASS | 1.00 to 0.40 with confirmed 0.60 exit; snapshot-only recovery stays unresolved |
| Scale-in | PASS | Confirmed deal quantities |
| Reversal | PASS | Flat/reopen separate epochs; INOUT closed/opened volumes, mixed episode excluded |
| SL modification | PASS | Null/value/change/removal; first-observed timestamps |
| TP modification | PASS | Null/value/change/removal; first-observed timestamps |
| Multi-EA | PASS | Three-candidate stress, multiple magics and position identities |
| Ambiguous attribution | PASS | Shared magic is not sufficient identity; exact comment binding tested |
| Manual/unknown isolation | PASS | UNKNOWN by default; excluded from EA-specific metrics |
| Trade episodes | PASS | Broker position plus close/reopen epoch; no speculative grouping |
| Replay determinism | PASS | Same raw frames yield same events, episodes, content IDs and exports |
| Restart recovery | PASS | Retained frame recovery and history overlap; failed history does not invent close |
| Market context | PASS | Content-addressed windows shared across nearby polls |
| Future-leakage protection | PASS | M1/M5/M15/M30/H1/H4 closed-bar boundary tests and export checks |
| Dataset export/content hash | PASS | Four Parquet datasets, manifest, readback and hash-tamper rejection |
| Dashboard EA Observer | PASS | Browser desktop/mobile review; fixture session, financial values and attribution |
| Read-only invariant | PASS | Observer SDK allowlist, GET-only API, no execution controls |
| Demo-only | PASS | Account identity/mode fail-closed integration tests |
| IP/licensing boundary | PASS | No EA binary access or reverse engineering |
| Observer targeted tests | 39 PASS | 28 unit cases and 11 PostgreSQL integration cases |
| Python/PostgreSQL total | 917 PASS | Includes 134 integration tests; zero failures/errors/skips |
| Frontend tests and quality | 65 PASS | TypeScript strict, lint, format and production build PASS |
| Ruff / format / strict mypy / secret scan | PASS | 217 formatted files; 181 typed source files; 279 files scanned |
| Phase 2B–4A.1 regressions | PASS | Full trusted chain; no historical simulations rerun |
| Frozen evidence | UNCHANGED | All 874 files byte-for-byte unchanged |

Final command: `scripts/verify_phase4_b.ps1`, exit code 0.
Log: `test-results/phase4_b-complete-gate.log`.
JUnit: `test-results/phase4_b.xml`, `test-results/phase4_b-targeted.xml`,
`test-results/phase3_6-frontend.xml`.
The composed chain reruns the full suite as required by its existing Phase 2B and
3.3B gates; 917 is the unique suite count, not a sum of those repeated executions.
Phase 3.3B verified the retained run, all 12 results and exact report. Phase 3.3C
verified four R-space and four synthetic results. Phase 4A.1 verified calibration
hashes, 144 profit rows, 24 margin rows, 144 risk scenarios and 131 retained deals.
The 24 Phase 3.4 files and 46 prior working files also remained unchanged.

## Final fake benchmark

Evidence: `.local/phase4_b/final/qualification.json`.
Normal session: `5978615e-717f-48f2-90f2-adab44fe4435`.
Stress session: `57284d81-1dd2-4346-8b17-1f12011b5467`.
Earlier captures in `.local/phase4_b/` and `accepted/` remain preserved.

| Measured field | 1 EA / 3 symbols | 3 EA / 12 positions |
| --- | ---: | ---: |
| Polls | 60 | 12 rapid modification polls |
| Wall seconds | 62.154138 | 32.731483 |
| CPU seconds | 16.843750 | 31.421875 |
| CPU percent of one core | 27.099966 | 95.998934 |
| Traced Python peak bytes | 1,108,298 | 1,346,460 |
| Raw observation frames | 16 | 12 |
| Behavior events | 27 | 192 |
| Database growth bytes | 270,336 | 229,376 |
| Errors | 0 | 0 |

Normal cadence target is one second; maximum measured poll was 1.725620 seconds.
CPU/wall/memory include tracemalloc instrumentation and exclude export time.
Memory is traced Python allocations, not process RSS or terminal/PostgreSQL memory.
Database growth is whole-database size delta, not exact per-session allocation.
Stress is a serial rapid-modification workload, not a one-second throughput claim.
Normal event rate extrapolation is 1,563.854/hour for this scripted scenario only.
Semantic event-storm criterion: changing quote/floating P/L without behavioral
change produces zero additional lifecycle frames/events; heartbeats are separate.

Both normal exports have identical canonical rows/order/IDs and identical bytes
under the pinned PyArrow writer. Manifest and per-dataset SHA-256/content hashes
are retained in the export manifests and independently verified. This is not a
cross-version Parquet byte-identity guarantee. Each dataset entry includes schema,
session, observer version, config hash, created_at, row count and hashes.
Created_at is the last raw observation time (empty session: session start).

## Recovery, evidence and metrics

Priority: confirmed broker history, current broker position, previous snapshot.
Snapshot disappearance is not a close; history failure leaves the poll degraded
without accepting fabricated state or realized profit. Preexisting snapshots
carry origin and null opening time; anchored episodes remain partial. A confirmed
opening deal may establish broker entry time. Stop changes carry FIRST_OBSERVED_AT.
INOUT records closed old and opened new exposure without inventing fee allocation.

Summary metrics exclude incomplete/ambiguous/unknown episodes. Known/unknown
duration counts include all confidently attributed external episodes; financial
known/unknown counts use eligible episodes. Null never means zero. The normal fake
session has one eligible completed episode and one excluded mixed reversal;
eligible gross observed P/L is 0.35 USD, commission -0.04, fee 0, swap 0.
These are fixture observations, not real EA performance.

| Normal fixture summary | Value |
| --- | --- |
| Eligible episodes / BUY / SELL | 1 / 1 / 0 |
| Eligible symbol counts | BTCUSDm: 1 |
| Entry lot min / median / max | 0.10 / 0.10 / 0.10 |
| Known holding seconds min / median / max | 30 / 30 / 30 |
| Known / unknown duration count, including partial episodes | 1 / 1 |
| First-observed SL / TP usage rate | 1 / 1 |
| Average first-observed SL / TP price distance | 5 / 10 |
| Scale-in / partial close / all-source reversal count | 1 / 1 / 1 |
| Eligible net observed P/L | 0.31 USD |
| Eligible financial known / unknown counts, each field | 1 / 0 |

Native read-only metadata probe at `2026-09-23T22:34:57.383236+00:00` confirmed
DEMO trade_mode 0, margin_mode 2 (hedging), terminal build 6182, Exness Technologies
Ltd / Exness-MT5Trial14. Evidence: `.local/phase4_b/account-mode.json`.
It did not start an EA or capture real external EA behavior. Netting is separately
qualified with deterministic fixtures; prior Phase 4A metadata is not overwritten.

Browser evidence: `test-results/phase4_b-browser.json` and observer desktop/mobile
screenshots. Both sizes had no page overflow or JavaScript exceptions. The observer
shows FIXTURE / FAKE-DEMO and STOPPED. The general monitoring header can independently
show stale historical telemetry; it is not the selected observer's connection state.

## Files added

24 added project files; generated local evidence is listed separately below.

- `PHASE4_B_REPORT.md`
- `config/external_ea_observer.example.json`
- `dashboard/src/ObserverPage.tsx`
- `dashboard/tests/observer.test.tsx`
- `docs/PHASE4_B_EXTERNAL_EA_OBSERVER.md`
- `scripts/qualify_phase4_b.py`
- `scripts/verify_phase4_b.ps1`
- `scripts/verify_phase4_b_evidence.py`
- `src/trading_ecosystem/observer/__init__.py`
- `src/trading_ecosystem/observer/__main__.py`
- `src/trading_ecosystem/observer/api.py`
- `src/trading_ecosystem/observer/context.py`
- `src/trading_ecosystem/observer/contracts.py`
- `src/trading_ecosystem/observer/export.py`
- `src/trading_ecosystem/observer/identity.py`
- `src/trading_ecosystem/observer/native.py`
- `src/trading_ecosystem/observer/replay.py`
- `src/trading_ecosystem/observer/runtime.py`
- `src/trading_ecosystem/observer/store.py`
- `src/trading_ecosystem/observer/summary.py`
- `tests/integration/test_external_observer.py`
- `tests/observer/__init__.py`
- `tests/observer/fixtures.py`
- `tests/observer/test_replay.py`

## Files modified

4 existing project files, solely for dashboard integration and verification.

- `dashboard/src/App.tsx`: add EA Observer navigation and page integration.
- `dashboard/tests/components.test.tsx`: replace obsolete six-page count with
  exact seven-page names and verify EA Observer mock isolation; retain Risk and
  prohibited trading-control checks. The first gate found this expected UI
  integration mismatch; no product code or benchmark behavior changed to fix it.
- `scripts/verify_phase4_a.ps1`: accept only named, reviewed integration paths
  supplied by the new gate; default frozen protection remains unchanged.
- `scripts/verify_phase4_a1.ps1`: propagate that narrowly scoped integration list.

No accounting/risk formulas, frozen simulator/results, datasets or broker
calibration semantics changed. No previous tests were weakened. Generated exports,
benchmark records, local metadata probe, browser helper scripts/screenshots and
gate logs stay Git-ignored under `.local/phase4_b/` and `test-results/`.

## Known limitations and stop point

- Real external EA identity/metadata was not provided: qualification remains blocked.
- Attribution depends on explicit registry evidence; magic/comment alone are not proof.
- Original entry time, historical stops/account equity and missing fills may be unknown.
- Reversal fee allocation/grouping is deliberately unresolved; mixed episodes are excluded.
- Bar windows may be PARTIAL; chart-bar basis remains unverified. MAE/MFE and risk
  fraction remain null. No indicators, regime labels, rankings or inferred strategy.
- Every behavioral change currently replays the retained session. Long sessions,
  large histories and slow native context reads need separate performance qualification.
- Dashboard lists at most 50 sessions and bounds metrics to 20,000 events/2,000 episodes;
  incomplete metrics are labeled. Full export/replay is authoritative.
- PostgreSQL raw evidence contains broker observations; the API remains loopback-only.
- Existing Phase 4A.1 economics readiness stays PARTIAL / sizing_ready false.
- The preserved Phase 3.3B verifier emits a Pydantic model_fields deprecation warning;
  it is non-failing and its frozen implementation was not changed.

Stop before Phase 4C. Implementation completion is separate from real EA qualification.
