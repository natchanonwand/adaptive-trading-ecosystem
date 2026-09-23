# Phase 4B — External EA Observer & Behavioral Capture

This is a DEMO-only, read-only observer. It neither installs nor activates EAs,
creates broker requests, modifies positions, nor inspects proprietary binaries.
The Phase 4A.1 checkpoint is `5f25848`. Broker economics and risk sizing readiness
are unchanged: PARTIAL / false. No inference, strategy classification or Phase 4C
features are produced.

## Data flow and ownership

`observer.native.NativeObserverClient` reuses the existing SDK loader and read
methods. The only additional read method is `copy_rates_range`, already used by
the repository's discovery infrastructure. Account `margin_mode` and order SL/TP
fields are observed explicitly. No calculator is required by the observer.

Raw frames and deduplicated bar windows use the existing `mt5_readonly.observations`
table, under a new DEMO scope containing the observation session ID. Original
Phase 4A observations, journals, checkpoints and calibration captures are not
modified. The additive `external_ea` schema holds immutable session configuration,
ordered frame references, rebuildable lifecycle events and rebuildable episodes.
Its idempotent installer follows the existing MT5 schema convention and requires
the monitoring migration. It does not alter historical migration heads.

Each frame records normalized account, positions, active/history orders, new
deals, quotes, instrument metadata and context references. Decimal strings stay
exact across PostgreSQL, JSON and Parquet. Raw hashes and sequence conflicts fail
closed. Transactional session locking rejects concurrent conflicting writers.
Derived rows may be rebuilt; raw evidence is never rewritten.

## Registry and attribution

`config/external_ea_observer.example.json` starts with an empty registry. Candidates
are metadata/reference records: ID, display name, vendor, version, magic numbers,
symbols, optional exact comment, status and notes. Do not store EA binaries or
credentials. Copy local configuration into `.local/phase4_b/` for actual metadata.

A unique magic/symbol match alone is PROBABLE with source UNKNOWN. KNOWN source
classification requires an explicit exclusive binding and attribution reference.
Multiple matches are AMBIGUOUS. Magic zero is not automatically manual, and
unmatched sources stay UNKNOWN. MANUAL and INTERNAL_STRATEGY require the same
explicit evidence. Ambiguous, incomplete or unknown episodes are excluded from
EA-specific metrics by default. Multiple candidate identities coexist in one
session; there is no global current EA.

Observed source instances retain broker, server/account scopes, magic, comment,
symbol, attribution evidence and first/last observed timestamps. Account scope is
pseudonymous; it is not a native login or credential.

## Lifecycle and recovery

Deals reconstruct quantity changes by broker position identity. Orders, deal
facts and position snapshots remain distinct. Active order changes/removals and
historical order state are captured without inferring a fill from disappearance.
SL/TP initial observation, change and removal carry old/new values and
FIRST_OBSERVED_AT. Snapshot disappearance alone is not labeled a completed close.

History overlap deduplicates deal tickets; conflicting immutable deal contents
fail. Same-time fills use a deterministic ticket tie-break, explicitly not proof
of exact causal ordering. Multiple hedged positions are never merged merely
because magic, symbol or direction match. Netting/exchange modes reject multiple
simultaneous position identities for one symbol.

Conservative episodes follow one broker position and a close/reopen epoch. A
reversal is retained as a mixed-direction episode, marked ambiguous and excluded
from EA-specific metrics rather than inventing fee allocation or basket grouping.
Initial pre-existing exposure is left-censored. A previously observed position
can anchor a recovered reduction/close, but cannot establish its original entry
time: holding duration remains unknown. Missing intermediate SL/TP changes are
not fabricated. Restart or failed-poll recovery is explicit on subsequent facts.

Evidence precedence is broker deal/order history, then current broker position,
then previous observer snapshot. Order state alone does not prove a fill.
An anchored preexisting episode has `origin=PREEXISTING`, `opened_at=null` and
`holding_seconds=null`; its observed close can still be confirmed by an exit deal.
Snapshot-only volume changes use RECOVERED_STATE, never an invented fill sequence.
INOUT reversal records closed old volume and opened new volume in one event while
retaining an ambiguous mixed episode; fees are not allocated to invented subepisodes.
LONG-flat-SHORT confirmed fills create separate close/reopen epochs.

Summary duration known/unknown counts cover all confidently attributed external
episodes, including incomplete ones. Financial totals and their known/unknown
counts cover eligible episodes only; excluded episode counts are explicit.
Null duration and financial values are never converted to zero.

## Context and future leakage

Important observations carry bid/ask/spread context and references to 50 closed
bars (configurable 50–200) for M1/M5/M15/M30/H1/H4. Windows are content-addressed
and reused. Poll-time facts and broker deal times are separate. A quote later
than the event, or older than five seconds, is unavailable for that event.
Bar open time plus timeframe duration must be at or before the event cutoff.
Current incomplete candles are excluded. Export readback independently checks
those bounds and links.

Historical entry quotes, original SL/TP and historical account equity cannot be
invented from current position/account state. Poll-time account/position snapshots
are retained with their own time basis, not silently promoted into historical
entry features. Bar retrieval errors or insufficient terminal history produce
explicit PARTIAL windows. Session label remains UNKNOWN; UTC time/day are raw
context. Chart-bar basis remains unverified. MAE/MFE are unavailable and deferred.

Entry/exit deal quantities and prices, position SL/TP snapshots, signed observed
profit/commission/fee/swap, entry sequences and raw timing support future feature
work. No risk percentage, martingale/grid/trend label, alpha, ranking or strategy
logic is asserted.

## Polling and operational limits

Default position/order/account sampling interval is one second; configurable
250–1000 ms. History reconciliation defaults to three seconds, configurable 2–5.
The loop sleeps and never spins. Quotes and context windows are fetched on behavioral frame
changes. Floating price/P&L changes alone do not generate behavior frames.

The reference benchmark uses deterministic fake broker responses with real local
PostgreSQL: one candidate, three symbols, 60 one-second polls, a restart and
scripted lifecycle changes; then three candidates, 12 positions and rapid SL
modifications. CPU, traced Python peak memory, actual wall/max-poll time, database
growth and event rate are reported. Tracemalloc overhead is included. Memory is
Python allocations, not terminal/PostgreSQL RSS. Database growth is measured for
the local database and is not exact per-session storage allocation. Events/hour
is a scripted-sample extrapolation, not a forecast of an external EA's activity.

Replay currently rebuilds derived session rows after a behavioral change. Long
sessions need retention/performance review; fake stress is not a production
throughput claim. A slow context read may overrun the configured polling interval;
timestamps and measured maximum duration are reported rather than promising
subsecond capture. History outside the bounded overlap or beyond record limits
requires explicit reconciliation. The dashboard bounds summary/query rows and
labels incomplete metrics; full export/replay is the authoritative readback.

## Running and exporting

Set `TE_DATABASE_URL` locally to the existing migrated observation database.
Do not put credentials in arguments, configuration committed to Git or reports.

```powershell
.venv\Scripts\python.exe -m trading_ecosystem.observer `
  --config config/external_ea_observer.example.json --seconds 60 `
  --export .local/phase4_b/new-session-export
```

Only attach when the intended account is already DEMO; no login/account switch
or EA activation is performed. `--resume <session UUID>` requires identical
account scope and configuration. A new export directory is required every time.
The API is loopback GET-only on port 8765; the existing dashboard proxy remains.
The EA OBSERVER page polls its read-only endpoint every two seconds, separately
from internal strategy activity. No GPT or execution controls are present.

Exports contain `external_ea_events`, `external_ea_episodes`,
`external_ea_market_context` and `external_ea_raw_frames` Parquet files plus a
manifest. Versioned schema, canonical JSON, SHA-256, content identities, session,
config identity, source instances and descriptive summary support exact replay.
Parquet output is deterministic under the pinned PyArrow version. Accepted fake
evidence lives in `.local/phase4_b/final/`; earlier benchmarks in `accepted/` and
its parent are preserved. Each dataset manifest entry includes schema/session/
observer versions, config hash, created_at, row count, file hash and canonical
content identity. `created_at` is the last raw observation (or empty session start),
not wall-clock export time, so repeated exports remain deterministic.
All exports are outside frozen evidence.

```powershell
# Explicit fake qualification, without any MT5 attachment:
.venv\Scripts\python.exe -m scripts.qualify_phase4_b
# Full prior-phase and observer gate:
.\scripts\verify_phase4_b.ps1
```

The old Phase 4A/4A.1 verifiers retain their default protection and accept only
three named, explicitly reviewed integration paths when invoked by the new gate.
The new gate checks the entire `5f25848` checkpoint with a four-file integration
allowlist and checks its files again after the composed gate. Dataset/research
integrity checks and all old tests remain intact.

Real external EA smoke remains BLOCKED / NOT PROVIDED unless an already running,
authorized DEMO candidate and attribution metadata are supplied. Deterministic
fake qualification is never described as real external EA behavior.

Stop before Phase 4C, inference, cloning, parameter optimization or execution.
