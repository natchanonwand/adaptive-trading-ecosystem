# Phase 2A: broker and market-data discovery

Status: owner-authorized read-only discovery after frozen `phase1-v0.1.0`. This subphase establishes observations for D01 and investigates D02. It does not implement Phase 2B ingestion, indicators, strategy, risk execution, simulation, paper/demo execution, UI, news, ML or broker writes. The V0 assets and disabled entry guard are unchanged.

## Provider and safety boundary

The optional `discovery` dependency extra installs the official MetaTrader5 package only on Windows. Only `discovery/sdk.py` imports it. The provider, consumers and future backtester exchange immutable internal contracts, never SDK objects or namedtuples. Source scope tests permit only the explicitly named discovery functions and constants on the native SDK object. The provider offers identity, account environment, instrument catalog, metadata, latest quote, bounded bars/ticks and coverage probes.

Initialize attaches to existing terminal state without credentials or an account-switch interface. Before any catalog/market read and after every read, check connected terminal status and the actual account `trade_mode` integer: only DEMO (0) is accepted. REAL, CONTEST, unknown, missing, boolean or textual modes fail. A server name containing “demo” is insufficient. On failure, stop discovery, disconnect the Python bridge, discard collected observations, and write sanitized BLOCKED envelopes rather than stale observations. Shutdown disconnects the Python API; it does not close the user's terminal.

Allowed native capabilities are initialize, shutdown, account_info, terminal_info, symbols_get, symbol_info, symbol_info_tick, symbol_select, copy_rates_range, copy_ticks_range and last_error. This implementation does not need last_error: arbitrary native diagnostic text is suppressed. `symbol_select(symbol, True)` may enable a symbol in the terminal's Market Watch; this explicitly permitted local selection is the only terminal-state change beyond API initialization/shutdown. Selected symbols remain visible. No account/position/order mutation API is exposed.

The installed upstream SDK necessarily contains more functions than this wrapper permits. Safety evidence concerns the application's reachable read-only interface and source allowlist, not a claim that MetaQuotes removed trading functions from its binary. Phase 1 entry permission remains disabled for all asset/mode combinations. There is no LIVE runtime mode.

## Privacy and identity

Extract account fields using an explicit allowlist: company, server, currency, trade_mode. Never extract account login, account holder name, password or complete native record representations. Terminal extraction is limited to connected and maxbars. Exception messages use fixed failure codes without underlying text/context; CLI output is status/progress only. Tests use synthetic broker labels and opaque private-field sentinels, never account identifiers or credentials.

All five local JSON artifacts are under Git-ignored `data/discovery/`. The secret scanner also rejects this directory if someone force-stages it. Only separately sanitized synthetic fixtures may be committed outside that directory. A reviewed report may contain the four owner-permitted broker identity fields and instrument/history observations; no account ID or credential is included.

## Symbol candidates and metadata

Search catalog names and descriptions for Bitcoin/USD, gold/USD and US technology-100 aliases. Broad matches are suggestions, not equivalence: exclude Bitcoin Cash from Bitcoin-description matches; retain distinct micro, quote-currency and scaled alternatives as unapproved candidates. Every match, including an exact canonical name, is BLOCKED pending explicit owner approval. Multiple matches carry an ambiguity reason. There is no automatic approval function or configuration flag.

Collect descriptions, paths and base/profit/margin currencies plus digits, point, tick size/value/profit/loss values, contract size, lot min/max/step/limit, stop/freeze distances, calculation/trade/execution/filling/order modes, swap mode/long/short/triple-rollover day, and current bid/ask. Integer enumerations remain integers. Source floating-point numeric values convert once through `Decimal(str(value))`; internal monetary observations are Decimal and serialize as decimal strings. Missing, malformed or nonfinite values are null and explicitly listed. A returned zero is retained as observed, not replaced by a guessed value; present fields alone do not establish usable valuation/protection constraints. Metadata is a current UTC snapshot, not effective-dated historical truth.

Latest quotes require positive finite bid and ask; malformed values fail. Crossed positive quotes are retained with a crossed flag for quality reporting, never treated as executable. Historical malformed numeric fields are counted, not repaired. `time_msc` is preferred; seconds are used only when milliseconds are unavailable. Both normalize to UTC without binary-float timestamp arithmetic.

## Probe policy

Take a fixed run `as_of` at the latest UTC hour. Every requested interval is half-open `[start,end)`; subtract one millisecond at the native inclusive end and filter returned timestamps again. No forming H1 bar is included. The bar API permits at most 366 days per request; the tick API permits at most one hour. No raw row history or qualified dataset is saved.

- H1: request progressively 7, 30, 90 and 365 days. Record actual minimum/maximum bar-open times, row count, duplicate timestamps, invalid OHLC and malformed time count. None/error differs from an empty successful result. Do not infer missing-session corruption before calendar qualification. Price basis remains UNVERIFIED_BROKER_OHLC until D02 validation.
- Ticks: requested intervals are trailing 1, 7 and 30 days, plus individual sample days starting 30, 90 and 365 days ago. Fetch hourly slices from the interval start. Stop at 100,000 retained ticks or 48 requests per probe, whichever comes first. The run retains at most 2,000,000 ticks for statistics; one SDK call materializes at most 100,001 normalized records so overflow is detectable. The upstream SDK may allocate more raw rows within that one-hour request; Python keeps only the bounded prefix. There is no multi-year request.
- Record first/last observed ticks, bid/ask presence, malformed/crossed quotes, duplicate timestamp count/groups/max multiplicity, timestamp precision, query count and the completely processed interval prefix. BUDGET_LIMIT is explicitly partial. A boundary chunk may contain retained ticks beyond `processed_until`, which denotes only fully examined chunks; first/last observed times remain accurate. `requested_interval_fully_queried` describes requests, not proof of continuous data coverage.
- Source sequence information is UNAVAILABLE: native row order and tick flags are not authenticated source sequence IDs. Equal-millisecond observations are counted without inventing chronological causality. Every result has `continuous_coverage_established=false`, even if a sample succeeds.
- At most three candidates per asset are probed, ranked by exact name, USD profit currency, expected base currency, shorter symbol name, then lexical order. Assets are visited round-robin. Ranking is a resource policy, never mapping approval. All candidates receive metadata discovery; unprobed alternatives/budget exhaustion must remain explicit in the report.

## Artifacts and acceptance

`provider_identity.json`, `symbol_candidates.json`, `instrument_metadata.json`, `bar_coverage.json`, and `tick_coverage_probe.json` share schema version, run ID, plan/as-of, status and sanitized data. Each file is replaced atomically; consumers must reject mixed run IDs after interruption. A catalog-only diagnostic run explicitly marks history not run. [PHASE2A_REPORT.md](../PHASE2A_REPORT.md) records the complete run, suitability caveats, remaining D01/D02 decisions, commands, and test evidence.

Acceptance requires all Phase 1 regressions and new discovery tests, Ruff, strict mypy and secret scan; a connected DEMO account; candidate discovery; executed bounded H1/tick probes; no private fields in outputs; ignored artifacts; and no trading capability or later-phase implementation. Availability or suitability may remain blocked without fabricating data. Non-DEMO connection makes Phase 2A BLOCKED and prohibits further terminal discovery. Stop after this subphase.

## Primary references

The official [account_info reference](https://www.mql5.com/en/docs/python_metatrader5/mt5accountinfo_py) defines current-account inspection. The [symbol_info reference](https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfo_py) describes symbol properties. The official [bar-range documentation](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py) documents UTC bar times and terminal chart-history limits; [tick-range documentation](https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py) describes COPY_TICKS_INFO and UTC tick data. The dependency is the official [MetaTrader5 package](https://pypi.org/project/metatrader5/), not a third-party wrapper.
