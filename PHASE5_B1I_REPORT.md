# Phase 5B.1I — offline real-tick reconciliation

Status: IMPLEMENTATION AND OFFLINE RECONCILIATION COMPLETE / PASS.
Final full gate and independent preservation/readback verification passed.
Required immutable baseline: `phase5b-tooling-v0.1.11`, commit
`c78a7ed46f0c846d9aeffa345b8c08451ce028ac`.

## Findings and semantics

The preserved build-6230 HTML contains the structured label/value pair
`History Quality: 100% real ticks`. The percentage was present in the report, not in
the native journal searched by the frozen validator. The report contains 53,200,842
ticks, 34,651 bars and `M5 (2026.01.01 - 2026.06.30)`. Its header identifies build
6230; there is no separate labelled Model or Modeling Quality field. The execution
configuration and native journal independently establish the requested/running
real-tick model. Running that model alone does not prove full coverage.

The extractor now separates requested model, observed native model, history/modeling
quality, explicit real-tick percentage, provenance/confidence, fallback/unavailability,
counts and interval evidence. Equivalent explicit real-tick label/value forms are
supported. Generic `100%` History/Modeling Quality is insufficient. Partial coverage
fails the existing full-real-tick requirement; absence of coverage evidence becomes
`REAL_TICK_EVIDENCE_UNVERIFIED`, not positive unavailability. Conflicting evidence
cannot pass. The existing boolean log helper delegates to the typed extractor.

No generated-tick fallback or positive unavailability was found in the preserved
acceptance journal. This report's explicit coverage establishes
`REAL_TICK_COVERAGE_VERIFIED_100` at native-report evidence confidence; it is not an
independent audit of every broker tick.

Four referenced graphics (balance, history, MFE/MAE and holding graphs) were not
retained by the frozen capture/cleanup path and are absent from the pinned profile.
No graphics were reconstructed or OCRed. Coverage is explicit HTML text, not an
inference from a graphic.

The normal parser initially rejected a Deals table's `Symbol` column heading as a
duplicate of the `Symbol:` setting. The narrow correction consumes colon-labelled
metadata/value fields; duplicate labelled metadata remains an error. The first
insufficient-report assessment is preserved, and the final record links to it.

## Immutable execution and derived assessment

- Original BaselineRun: `aebb719c-6738-4b1a-a323-3f405ed512fe`.
- Candidate: `d5508913-c5d6-4f97-99e2-0be7e859b84a`.
- Original execution outcome remains `BLOCKED_REAL_TICKS_UNAVAILABLE`.
- Reconciled assessment: `REAL_TICK_COVERAGE_VERIFIED_100`.
- Recovery: `OFFLINE_PARSED_NOT_PUBLISHED_IMMUTABLE_RUN`.
- Execution strategy: `INSTALLED_PROFILE_REFERENCE`.
- Phase 5B.1I native launches: zero. The acceptance lineage remains one actual
  candidate execution and one new acceptance run (three historical BaselineRuns
  total). This phase creates no BaselineRun, BaselineResult or configuration update.

The blocked run has no valid transition to COMPLETE under the existing contract.
Offline normalized data is therefore stored only inside the append-only derived
assessment with `POST_RUN_OFFLINE_RECONCILIATION` provenance. It is not inserted
into `baseline_results` or presented as execution-time output. Publishing this as a
product result requires an explicit reconciliation-result storage/API/UI contract
that leaves the original execution history intact. No invariant was relaxed.

## Identities and raw-byte limitation

| Evidence | Identity |
|---|---|
| Artifact SHA-256 | `ea21fcd96c9c5683aaf39fc20cf91cc29234f72ac22f202f726fe30e9d028ce4` |
| Configuration ID | `4a6d8cc7-59ef-474e-8eff-feec6d1658de` |
| Configuration identity | `2e31959d4f4b4e63151c2b1e7be1c3eb4058a06348b163a89d2950f4d271edfc` |
| Execution plan | `6178e755b74ff71da2eca2f8af2333ee867e27378b689edb3931e1d2c5c8de35` |
| Native raw report hash recorded at capture | `eb855831763c4b45a5463518b2e22f743146a9808b9b6ff4d67178c56516bc42` |
| Preserved UTF-8 report SHA-256, directly rehashed | `d36024464fcd14606c243c8a29441898fa4543f2b09f2af5ec51295658496eed` |
| Original run manifest | `0e75aef15a1b9ee72d70b39a7593e0a49937e237fa05b0d0ae296c3e4e92ea7e` |
| First assessment | `b33be9a49ea813768d9c25bc5f065bb17527314620f75009f722bcf757b469e0` |
| Final reconciliation | `b4fe6d5c7b8d05c19d1f79acbf2f1f413c44967c793ca28ea99128144cac9d64` |
| Offline normalized identity (not a database BaselineResult) | `1d63190e84549d2083cd863a7ffbf082946e495b0e9c95d88a8108a3339712f4` |

The original encoding bytes were not retained by the frozen adapter. Their recorded
digest is verified through unchanged manifest-bound provenance; it cannot be freshly
rehashed against an absent original file. The preserved UTF-8 report and all retained
native logs are directly byte-verified. They were not edited during reconciliation.

Derived artifacts: `.local/phase5_b1i/reconciliation-final/assessment.json` and its
manifest. The original run namespace and the earlier assessment remain unchanged.

## Offline normalized observations

| Metric | Preserved report/parser value |
|---|---|
| Initial deposit | 300.00 USD |
| Total / winning / losing / long / short trades | 0 / 0 / 0 / 0 / 0 |
| Net profit / gross profit / gross loss | 0.00 / 0.00 / 0.00 |
| Profit factor / expected payoff | 0.00 / 0.00, as reported |
| Balance / equity maximal drawdown | 0.00 (0.00%) / 0.00 (0.00%) |
| Largest / average profit or loss trade | 0.00, as reported |
| Maximum consecutive wins / losses | 0 / 0 |
| Average / maximum holding time | 0:00:00 / 0:00:00 |
| Win rate | unavailable (`null`); no division by zero or invented value |

No judgment, strategy inference, optimization, parameter recommendation or comparison
is made from these values. BaselineResult ID: none.

## Validation and scope

Final complete Phase 5B gate: PASS (`.local/phase5_b1i/full-gate-3.log`).

| Check | Result |
|---|---|
| Backend regression | 1,432 passed; no failures/errors/skips |
| PostgreSQL/integration, including migrations | 283 passed, included in backend total |
| Frontend regression | 105 passed with frozen worker configuration |
| Ruff / format / strict mypy / secret scan | PASS; mypy checked 295 source files |
| Frontend typecheck / lint / format / production build | PASS |
| Scope / Git-ignore / frozen lineage / git diff --check | PASS |
| Frozen research evidence | 1,044 files byte-identical |
| Historical evidence including original acceptance | 1,587 files byte-identical |
| Original database | All seven tables unchanged; 3 existing runs, 0 results |
| Reconciliation readback | Deterministic recomputation equals saved final assessment |
| Git HEAD / origin/main / prior tags | Unchanged; no commit/tag/push |

Gate SHA-256: `095683dad69d178e1b3e241e8b77a320f10efddd1822736a8021fc1a58f49c01`.
Added tests: 28 offline/unit cases and 4 PostgreSQL integration cases. Focused offline
test run: 89 passed including existing parser tests. Final audit:
`.local/phase5_b1i/final-verification.json`.

Coverage includes configured mode versus real coverage, absent percentage, explicit
100%, partial/zero coverage, fallback, unavailability, conflicting evidence, equivalent
HTML representations, raw hash tampering, duplicate metadata versus Deals headings,
offline parser recovery/failure, provenance, exclusive persistence, immutable run
outcome, zero native execution, unchanged PostgreSQL run/result/configuration rows,
and no synthesized metrics.

Changed files:

- `src/trading_ecosystem/tester/tick_evidence.py`
- `src/trading_ecosystem/tester/reconciliation.py`
- `src/trading_ecosystem/tester/adapter.py`
- `src/trading_ecosystem/tester/contracts.py`
- `src/trading_ecosystem/tester/parser.py`
- `src/trading_ecosystem/tester/service.py`
- `src/trading_ecosystem/tester/checkpoint.py`
- `scripts/verify_phase5_b_scope.py`
- `tests/test_phase5b_tick_evidence.py`
- `tests/integration/test_tick_reconciliation.py`
- `PHASE5_B1I_REPORT.md`

The scope verifier pins v0.1.11 and permits only this file set. Prior tags, frontend
worker configuration, prior tests and immutable research evidence are preserved.

UI debt remains separate: execution strategy and full start/end timestamps are not
exposed in the run detail; no reconciliation display or retro redesign was added.
Phase 5B functional product acceptance cannot yet close with a published BaselineResult;
real-tick evidence and offline parsing are qualified, while explicit derived-result
publication remains a product-contract decision.

Deviation/operational note: after the interrupted session, the existing local
PostgreSQL cluster was stopped. The first failed full-gate log is retained; restarting
the same cluster did not initialize/reset it or alter the research configuration.
The second gate passed all 1,432 backend tests but found one scope-file formatting
issue; formatting was corrected without behavior changes. The third complete gate
passed. Final database preservation and evidence checks also passed. Both earlier
gate logs and the initial parser-blocked assessment remain available unchanged.

No Gold Scalper rerun, new acceptance attempt, configuration change, Phase 5C,
forward trading, commit, tag or push is authorized or performed in this phase.
