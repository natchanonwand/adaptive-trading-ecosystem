# Data model

## Global conventions

Persist timestamps as timezone-aware UTC with microsecond precision; API text uses RFC 3339 with `Z`. Bars cover `[open_time, close_time)`; a bar becomes usable only after its close and `available_at`. Store source event time, receipt time, and availability time separately. Session boundaries come from versioned exchange/broker calendars converted to UTC, including daylight-saving transitions. Never use Bangkok midnight for accounting.

Use UUID entity IDs, immutable content hashes for artifacts, and a monotonic sequence per account event stream. Decimal prices, quantities, money, and valuation factors have explicit scale and unit; no binary-float monetary accounting. Feature arithmetic uses Decimal precision 34, round-half-even, no intermediate quantization, and a pinned arithmetic version. Quantize prices/volume only at instrument boundaries. Reject NaN, missing required units, or invalid denominators. For a long, round the signal stop down to a tick and the post-fill raw TP up to a tick: `take_profit = ceil(take_profit_raw / tick_size) * tick_size`. Do not round actual-fill VWAP before calculating initial price risk and raw TP. Record rounding delta and effective price RR; costs never enter the TP formula.

## Entities and required fields

| Entity | Required fields and constraints |
|---|---|
| Asset | `asset_id` in BTCUSD/XAUUSD/USTEC100, display name, quote currency USD; canonical identity distinct from broker instrument |
| InstrumentVersion | broker/server/symbol, effective interval, asset ID, base/quote/account currencies, contract size and units, tick size, tick value per lot, valuation model, lot min/max/step, stop distance, margin model, trading calendar/version, supported filling modes, SL/TP distance/freeze constraints and amendment/paired-protection capabilities; effective intervals cannot overlap |
| Bar | dataset ID, asset/instrument version, timeframe, open/close time, OHLC, optional volume and volume type, price basis, available/received times, quality flags; unique dataset+asset+timeframe+open time; H1 duration is 3600 seconds |
| Quote | instrument version, event/received/available times, bid, ask, source sequence for equal timestamps; ask ≥ bid > 0 |
| DatasetManifest | content hash, source/license, coverage, ordered file hashes, bar/quote basis, metadata/calendar hashes, gaps, transformations, ingestion version, validation result |
| NewsItem | source ID/URL, publisher, published time, first-seen time, available time, text hash, revision ID, asset tags, license; deduplicate source ID+revision |
| MacroObservation | series ID, observation period, release/available times, vintage ID, value/unit, source; revised values are new vintages |
| ResearchAnnotation | input source IDs, model/prompt version, generated time, summary, uncertainty, reviewer status; never executable |
| FeatureSnapshot | asset, bar close, available time, feature version/hash, ordered Decimal values, source manifest and input hash |
| RegimeObservation | feature snapshot, classifier version, label TREND/RANGE/HIGH_VOL/UNKNOWN, score semantics; diagnostic only in V0; classifier definition unresolved for later phase |
| StrategyRelease | immutable code/parameter/feature/runtime/metadata hashes, strategy name, risk policy hash, creation time, state, evidence IDs |
| QualificationEvidence | release hash, mode, dataset or forward stream manifests, registered windows, report hash, tests, pass/fail reasons, start/end times |
| Approval | release hash, evidence IDs, permitted mode/account, approving human identity, UTC time, expiry/revocation, signature or tamper-evident record |
| TradeIntent | release, asset, bar close (entry signals; nullable for asynchronous protection/exit events), action ENTER_LONG/SET_PROTECTION/EXIT, reason, proposed stop and reference price, `target_rr=2`, `target_basis=ACTUAL_ENTRY_VWAP`, `target_rounding=CEILING_TICK`, `take_profit=null` on original entry intent; derived protection/exit intents carry actual-fill TP, target_version and source fill IDs, exit reason when applicable, deterministic intent key; no broker credentials or final order volume |
| RiskDecision | intent ID, policy version, account snapshot/event sequence, quote ID, approved/rejected, reasons, final volume, fixed stop, target RR/basis/rounding, indicative TP (not final), post-fill actual VWAP/initial_price_risk/take_profit_raw/take_profit/target_version when validated, protection validation status, estimated costs/margin/risk, reservation ID, expiry; post-fill decisions append to the original admission lineage |
| RiskReservation | account, intent, amount/units, unfilled volume, state, creation/expiry times; release only on confirmed terminal or safe pre-submission expiry |
| OrderRequest | account, adapter, intent/risk IDs, idempotency key, side, volume, type (including protection amendment), fixed stop, target RR/basis/rounding, actual entry VWAP and initial_price_risk when known, take_profit_raw and `take_profit` (null before actual fills), target_version, parent entry request, source fill IDs, paired-protection IDs, exit reason, mode, release/approval IDs, durable created time |
| OrderEvent | request and broker order IDs, event sequence/type, broker/received times, status, confirmed SL/TP and target version, rejection/error, payload hash; append only |
| Fill | unique adapter+account+broker deal ID, request/order, instrument version, side, quantity, price, commission, execution time, received time, exit_reason and active target_version for exits, `intrabar_ambiguous` and simulation basis where applicable; partial fills distinct |
| Position | account+asset, release, quantity, weighted actual entry, fixed stop, initial_price_risk, take_profit_raw, take_profit, target_version, target_frozen, rounding_delta, effective_price_rr, independent SL/TP protection statuses and broker IDs, realized P&L, last reconciled sequence; derived projection |
| LedgerEntry | event ID, account, currency, amount, category CASH_FLOW/REALIZED_PNL/COMMISSION/FINANCING/ADJUSTMENT, reference ID, effective and recorded times; corrections reverse then replace |
| EquitySnapshot | account, time, ledger sequence, cash balance, bid-marked long unrealized P&L, equity, reserved/used margin, valuation quote IDs, stale flag |
| JournalEvent | account sequence, type, correlation/causation IDs, actor, mode, release, event/recorded time, schema version, payload hash, previous-event hash |
| TradeReport | episode/release/asset, entry and exit fill IDs/times, actual entry VWAP, fixed stop, initial_price_risk, initial_price_risk_usd, target_rr, raw/rounded TP, rounding delta/effective price RR, target-version history, gross/net P&L and costs, net_r, exit reasons/quantities (MIXED if multiple), normal/exceptional classification, intrabar_ambiguous |
| CalendarDay | mode/account, grouping timezone, start/end UTC, ledger boundary/snapshot ID, closed-episode net USD P/L, summed net R, closed trade count, win/loss state, equity P/L separately, per-asset results, episode/incident/annotation IDs, completeness flag; derived per REPORT_SPEC |
| Report | run/account, ledger boundary, release/manifests/policy, metric definition version, artifact hash, completeness warnings |

## Relations and accounting

Release → evidence → approval is immutable lineage. Intent → risk decision → order request → order events/fills → ledger/position projections → report is mandatory lineage. Original entry intents/decisions/requests remain immutable; post-fill protection intents, risk validations, and amendment requests append linked records. Native SL/TP exits reference the already approved bracket intent/request and active target version; they do not await a new risk admission at trigger time; exceptional exits reference their safety/operator/boundary reason; they still have an intent, risk decision, and order audit trail. Unknown broker fills remain explicit reconciliation exceptions until linked or resolved.

Balance is initial cash plus external flows, realized P&L, financing, commissions, and audited adjustments. Equity is balance plus unrealized P&L. Long positions mark to bid. Do not subtract spread a second time after bid/ask fills. Instrument-specific P&L and margin calculations must be validated against demo broker examples; unresolved conversion or valuation rejects entry. Initial USD account still requires instrument-provided valuation rules, not a hardcoded point multiplier.

A trade is an asset's flat-to-flat episode under one release, including partial fills and all attributable costs. For partial entries, actual-fill VWAP and target revisions follow [STRATEGY_V0.md](STRATEGY_V0.md); initial price-risk USD is the instrument-valued filled quantity loss from final entry VWAP to fixed stop, excluding costs. Exceptional pre-finalization exits preserve fill-level price-risk attribution. At most one episode per asset may be open. Pending entries count as occupied assets. Financing and commissions are allocated to the episode; unallocatable charges appear separately and prevent a fully reconciled report.

## Storage and quality

PostgreSQL stores relational metadata, approvals, operational events, and projections; immutable Parquet stores research bars/quotes. These are proposed technologies, not implemented tables. Foreign keys and unique constraints enforce lineage and deduplication. Backtests never overwrite source data. Late corrections create a new dataset manifest; forward decisions retain the original observed inputs.

Reject inverted OHLC, duplicate bars, crossed quotes, nonpositive prices, ambiguous timezone, out-of-session bars, and unversioned mappings. Distinguish scheduled closures from missing expected bars. Missing volume is allowed because V0 does not use volume. Missing price history blocks affected signals and triggers fresh warm-up as defined in [STRATEGY_V0.md](STRATEGY_V0.md).

Schema migrations require versioned readers, round-trip fixtures, and replay checks. News licensing, physical partition sizing, and finalized retention remain D02/D05/D06; they do not change these logical contracts.
