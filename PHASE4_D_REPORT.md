# PHASE 4D — BEHAVIORAL RESEARCH ENGINE

RESEARCH ENGINE IMPLEMENTATION: COMPLETE / PASS.
REAL EA RESEARCH QUALIFICATION: NOT PROVIDED.
Current analysis dataset: SYNTHETIC_QUALIFICATION.

Phase 4C was reviewed and scope, immutable feature rebuild and secret checks
passed before the authorized LOCAL checkpoint `90e9091`:
`feat: add leakage-safe behavioral feature engine`. No tag or push.
Phase 4D remains uncommitted and independently reviewable.

## Verification

| Requirement | Result | Evidence |
| --- | --- | --- |
| Dataset validation | PASS | Unchanged Phase 4C validator, exact byte readback and key joins |
| Synthetic guard | PASS | Empty hypotheses; SOFTWARE_VALIDATION_ONLY |
| Sample-sufficiency guard | PASS | Count/coverage/session/identity gates |
| Descriptive / temporal / direction | PASS | Known fixtures and denominator checks |
| SL/TP / volume progression / entry spacing | PASS | Null-aware numeric and conditional measurements |
| Market-context associations | PASS | Direction agreement, fixed bins, Spearman, Cramér's V |
| Outcome analysis | PASS | Retrospective strata; no Y injected into entry X |
| Behavior fingerprint / hypotheses / comparison | PASS | Versioned definitions; no classifications or rankings |
| Research report / GPT packet | PASS | Deterministic Markdown/JSON; no external API calls |
| Deterministic rebuild / canonical hashes | PASS | Two exports per preserved normal/stress source |
| False-inference adversarial fixtures | PASS | Random volume/spacing and imbalanced contexts |
| Phase 4D targeted tests | 64 PASS | 50 unit cases + 14 PostgreSQL integration cases |
| Python/PostgreSQL | 1,026 PASS | Includes 156 PostgreSQL integration tests; zero failures, errors or skips |
| Frontend | 75 PASS | Full frontend suite |
| Ruff / format / strict mypy | PASS | 263 formatted files; 223 typed source files |
| Frontend quality | PASS | TypeScript, lint, format, production build |
| Secret scan | PASS | 332 project files; no findings, including final report scan |
| Phase 2B–4C regressions | PASS | Unchanged composed verifier chain; all 12 retained research results verified |
| Historical evidence 874 | UNCHANGED | Final byte-for-byte hash comparison passed |
| Phase 4B evidence 53 | UNCHANGED | Includes preserved fake export evidence |
| Phase 4C evidence 57 | UNCHANGED | Includes retained interim and final feature evidence |

The full `scripts/verify_phase4_d.ps1` gate completed on 2026-09-25 with exit
code 0. `test-results/phase4_d.xml` records 1,026 tests. The composed verifiers
run the same full suite twice; the count is not doubled. The 64 targeted Phase 4D
tests are included in that total. Frontend XML is
`test-results/phase3_6-frontend.xml` (75 tests).
The unchanged Phase 3.3B verifier emitted a non-failing Pydantic `model_fields`
deprecation warning; all evidence checks completed successfully.

## Research outputs

Accepted qualification output namespace: `.local/phase4_d/final-v2/`.
Each normal/stress source is exported twice and independently rebuilt.
Each export has `research.json`, `behavior_fingerprint.json`,
`behavior_research_packet.json`, `report.md`, and `manifest.json`.
Runtime manifest timestamps are excluded from research content identity.

| Qualification measurement | Normal | Stress |
| --- | ---: | ---: |
| Observed episodes | 2 | 12 |
| Confirmed entry fills | 3 | 12 |
| Source sessions | 1 | 1 |
| BUY fraction / known denominator | 1 / 2 | 1 / 12 |
| Median entry volume / known count | 0.100 / 2 | 0.100 / 12 |
| Median holding seconds / known count | 30.00 / 1 | null / 0 |
| Generated behavior hypotheses | 0 | 0 |
| Sample tier | INSUFFICIENT | INSUFFICIENT |
| Analysis seconds including Phase 4C validation | 0.519176 | 0.867866 |

These are synthetic fixture measurements only, not EA behavior conclusions.
Timings exclude export/repeated readback, are untraced, and are not a throughput claim.
Both runs have status SOFTWARE_VALIDATION_ONLY.

- Normal run: `research4d-2de8808300f2bb495a7c3bb0`.
- Stress run: `research4d-f1cf9d05e48bd4479abdc3c6`.
- Exact content, artifact and manifest hashes are retained in
  `.local/phase4_d/final-v2/qualification.json` and each export manifest.
- `normal-repeat` and `stress-repeat` have identical canonical research artifacts;
  runtime manifest timestamps are intentionally allowed to differ.
- `comparison.json` contains descriptive differences with no ranking.

## Decisions and limitations

- The initial full regression found a Phase 3.1 scope conflict: its `research`
  directory permits mathematical primitives only. Phase 4D's new modules were
  moved to `behavioral_research`; no old scope test or kernel code was changed.
  Initial exports remain in `final/`, with their matching source snapshot in
  `interim-source/`. New source-derived identities use `final-v2/`. The initial
  failed gate log (1 failed, 1,025 passed) is preserved; the corrected full gate
  passed with 1,026 tests and its evidence is recorded separately.
- No real EA dataset was supplied. Synthetic output cannot establish behavior,
  performance, a strategy rule or an EA classification.
- Default evidence tiers 30/100/300 are configurable operational count labels,
  not calibrated quality thresholds. Hypothesis coverage, session and agreement
  thresholds are prespecified policy, not optimized or scientifically universal.
- Only three price/EMA direction-association hypotheses are instantiated for real
  inputs. All other requested families are represented in the future-facing
  schema and descriptive evidence where available; no martingale/grid label.
- Entry-only observations cannot estimate P(entry | context). Missing non-entry
  denominators are explicitly unavailable. Basket membership is also unavailable.
- Prior-loss pairing respects outcome availability and rejects tied predecessors;
  source-end availability makes most current-source pairs unavailable.
- Wilson intervals assume IID episodes; session bootstrap assumes independent
  sessions. These assumptions are not guaranteed. Intervals remain exploratory.
- No hypothesis significance tests or p-values were introduced. FDR significance
  testing, clustering, unrestricted rule mining and ADX are deferred.
- Raw-price and volume units differ across symbols; comparisons remain descriptive.
  No implicit economic normalization or winner ranking is performed.
- No shared dependencies, observer polling code, frozen features or risk/accounting
  formulas changed. Polling benchmark rerun is therefore not required; prior
  benchmark evidence remains preserved.
- Architecture, algorithms, bin definitions, thresholds and commands are documented
  in `docs/PHASE4_D_BEHAVIORAL_RESEARCH_ENGINE.md`.

## GitHub readiness and stop

Structured readiness metadata is generated from reports, XML test evidence and
package files into `.local/phase4_d/readiness.json`. It references architecture,
safety boundaries, assets, startup commands, screenshots and limitations.
No public README is created.

Only existing `dashboard/src/App.tsx` is modified to integrate Research Lab and
isolate its offline status. Prior tests/verifiers remain unchanged.

Added files (23):

- `PHASE4_D_REPORT.md`
- `docs/PHASE4_D_BEHAVIORAL_RESEARCH_ENGINE.md`
- `dashboard/src/ResearchPage.tsx`
- `dashboard/tests/research.test.tsx`
- `scripts/collect_phase4_d_readiness.py`
- `scripts/qualify_phase4_d.py`
- `scripts/verify_phase4_d.ps1`
- `scripts/verify_phase4_d_evidence.py`
- `src/trading_ecosystem/behavioral_research/__init__.py`
- `src/trading_ecosystem/behavioral_research/__main__.py`
- `src/trading_ecosystem/behavioral_research/analysis.py`
- `src/trading_ecosystem/behavioral_research/api.py`
- `src/trading_ecosystem/behavioral_research/contracts.py`
- `src/trading_ecosystem/behavioral_research/engine.py`
- `src/trading_ecosystem/behavioral_research/hypotheses.py`
- `src/trading_ecosystem/behavioral_research/loader.py`
- `src/trading_ecosystem/behavioral_research/reports.py`
- `src/trading_ecosystem/behavioral_research/statistics.py`
- `tests/behavioral_research/__init__.py`
- `tests/behavioral_research/fixtures.py`
- `tests/behavioral_research/test_engine.py`
- `tests/behavioral_research/test_statistics.py`
- `tests/integration/test_behavioral_research.py`

Generated research evidence and readiness metadata are ignored under
`.local/phase4_d/`. Final gate log: `test-results/phase4_d-complete-gate-v2.log`.
Browser checks: `test-results/phase4_d-browser.json` and desktop/mobile screenshots;
both sizes show the synthetic guard with no overflow or JavaScript exceptions.
A visual-review count-formatting defect was fixed and covered by UI assertions;
the research data and hashes were unaffected.

Stop for review. No Phase 4D commit, tag, push, GPT interpretation, real behavior
classification, strategy cloning/synthesis, optimization or execution.
