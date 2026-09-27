# Phase 5B.1A — MT5 environment calibration and initialization diagnosis

Status: DIAGNOSIS COMPLETE; native bootstrap BLOCKED_TESTER_CACHE.
Full regression result: PASS (final complete Phase 5B gate).
Gold Scalper acceptance retry is NOT safe/ready yet.

## Root cause and exact failure layer

The Phase 5B runner required `.local/phase5_b/environment.json`, but that file
was absent. Its loader caught the filesystem error and collapsed it to
INITIALIZATION_FAILED. Both retained attempts stopped in PREPARING, before
Adapter.prepare, candidate staging or native process creation:

- 7bbf2e42-fcc2-4782-8431-d1a3534f6742
- 2c4413d6-3cb6-4c07-9337-56374cc35226

Both retain INITIALIZATION_FAILED, observed status UNKNOWN, terminal build UNKNOWN,
null exit code and no result identity. There are no tester.ini, staged runtime,
report, stdout/stderr or native logs in either failed attempt. Neither attempt
reached RUNNING. Their historical states and all six evidence files are preserved.
This is not evidence of license denial, tester-access denial, symbol incompatibility,
missing real ticks or EA OnInit failure.

## Discovery and binding

Prior successful read-only evidence was reused from
`.local/phase4_a/demo-smoke-accepted.json`: DEMO, Exness Technologies Ltd,
Exness-MT5Trial14. That evidence did not supply a pinned tester executable path.
Deterministic installed-terminal discovery found one terminal, with exactly one
matching MetaQuotes origin.txt data-root mapping. No first-of-many selection occurred.
The SDK was not initialized, and no account credential/profile was copied.

| Field | Actual finding |
| --- | --- |
| Binding ID | 0b14ea86-61b9-4f0f-b9dd-ac766c6166df |
| Executable | C:\Program Files\MetaTrader 5\terminal64.exe |
| Existence/read access | PASS |
| Product/company | MetaTrader 5 Client Terminal / MetaQuotes Ltd. |
| File version/build | 5.0.0.6230 / 6230, from executable version resource |
| Prior read-only build | 6182; historical only, not used as current identity |
| Classification | RESEARCH_STRATEGY_TESTER_ONLY; not broker-order authorization |
| Data root | C:\Users\natch\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075 |
| Profile association | origin.txt resolves to the selected installation directory |
| Server cache | data root\bases\Exness-MT5Trial14 |
| Native tester executable | metatester64.exe exists alongside terminal64.exe |

Executable SHA-256: `602b2f42f2219a9d33ddcb3d935d85fddd92033d9eaccc5fea3f2285b389ce44`. <!-- pragma: allowlist secret -->

The pinned executable SHA-256 is recorded in the Git-ignored binding and diagnostic
snapshot, not treated as a vendor license attestation. Binding fields include UUID,
executable/hash, data root, company/product/build, discovery source, verified_at and
research classification. Login, password, tokens and account profiles are excluded.

## Cache and filesystem diagnosis

The pinned cache contract means the exact selected installation's server directory,
with symbols.raw and the explicitly bound symbol's .hcc history and .tkc tick files.
The actual XAUUSDm history directory is readable, including 2026.hcc; ticks contain
monthly 202601.tkc through 202606.tkc (and later months). Filenames do not prove
complete tick coverage or successful tester execution.

The actual server directory has a symbols subdirectory with symbols-*.dat and
selected-*.dat. It does NOT have the symbols.raw required by the existing isolated
adapter. BLOCKED_TESTER_CACHE therefore identifies an unsupported cache layout,
not proof that real ticks are unavailable. No .dat file was renamed, decoded or
silently substituted. No cache, account profile or Marketplace EA was changed.

Source file reads succeeded under the operator account. The data-root ACL grants
the current user full control. Tool sandbox access denial was independently checked
outside that sandbox and was not misclassified as an MT5 filesystem failure.
Generated diagnostic files were written only under the repo's ignored .local paths.

## Configuration validation and process boundary

A diagnostic-only INI was generated at `.local/phase5_b1a/diagnostic-tester.ini`,
from the existing saved configuration. Independent explicit field checks and strict
INI parsing passed. No saved configuration value was changed.

| Tester setting | Validated value |
| --- | --- |
| Expert | Existing run UUID-derived .ex5 basename; no candidate staged |
| Symbol / Period / Model | XAUUSDm / M5 / 4 (real ticks) |
| From / To | 2026-01-01 / 2026-06-30 |
| Deposit / Currency / Leverage | 300 / USD / 1:100 |
| Inputs | TESTER_DEFAULTS; no hidden values invented |
| Report | UUID-derived relative .htm basename inside the isolated runtime |
| Optimization / forward / cloud / remote | Disabled |
| Live trading / DLL imports / startup Expert and Script | Disabled / empty |
| ShutdownTerminal / ReplaceReport | 1 / 0 |

Actual failed-run process arguments, working directory, stdout/stderr and exit code
are NOT AVAILABLE because no process was created. Intended baseline arguments remain
a structured list: /portable and /config:<absolute tester.ini>; working directory
is the new attempt's isolated terminal directory. No shell interpolation is used.
No report file exists and none is claimed as generated.

The ENVIRONMENT_BOOTSTRAP_PROBE contract was evaluated after binding diagnosis.
Probe 9d0df5da-ebae-4b6a-9f1e-c6dc5b1ebf40 stopped at cache preflight:
BLOCKED_TESTER_CACHE, process_created=false, baseline_result=false. No native MT5
or Strategy Tester was launched. This satisfies the authorized precise-blocker stop
condition; it does not claim bootstrap success. The isolated terminal-only probe
implementation has a 10-second owned-process limit, no Expert/Script, no copied
EA/profile/account, and no BaselineRun/Result persistence. Process-start failures
and immediate exits are separately reported; survival alone is not initialization proof.

## Product changes

The existing Environment/adapter contract now consumes a pinned terminal-binding
sidecar when present. It verifies terminal hash, safe local paths and cache readiness.
Workbench displays Research Environment, selected terminal/company/build and typed
status, and disables the new Run Baseline action while the environment is blocked.
No large settings product or parallel broker connection system was added. No operator
selection is needed for the single unambiguous installation discovered here.

## Files changed

Modified:
- src/trading_ecosystem/tester/adapter.py
- src/trading_ecosystem/tester/service.py
- src/trading_ecosystem/tester/api.py
- src/trading_ecosystem/tester/contracts.py
- dashboard/src/workbench/ReadinessPanel.tsx
- dashboard/src/workbench/api.ts
- dashboard/tests/readiness.test.tsx
- scripts/verify_phase5_b_scope.py

Added:
- src/trading_ecosystem/tester/environment.py
- src/trading_ecosystem/tester/bootstrap.py
- tests/test_phase5b_environment.py
- PHASE5_B1A_REPORT.md

Operational evidence: `.local/phase5_b1a/` and
`.local/phase5_b/terminal-binding.json`, all Git ignored.

## Tests and remaining blocker

New synthetic tests cover valid/missing/ambiguous terminals, hash mismatch, missing
data/cache, unsafe relative paths, terminal build capture, forbidden secret fields,
invalid INI settings, structured process arguments, process-start exceptions,
immediate exit, preserved historical failure bytes and no result creation by probes.
A frontend test covers environment-blocked display independently of candidate readiness.
The complete old backend/PostgreSQL/frontend/frozen-evidence gate remains required.

Before a future acceptance retry, the current MT5 symbol-cache layout needs a verified,
credential-free isolated bootstrap contract. Do not treat .dat as .raw or assume a
successful historical SDK attach proves the portable native tester works. Once that
blocker is resolved, bootstrap still needs actual native verification; any acceptance
retry must use a new run ID and retain the saved research parameters.

Deviations: none. The precise remaining typed blocker is used instead of claiming a
successful native bootstrap. No Gold Scalper rerun, optimization, broker writes,
forward trading, Phase 5C, commit, tag or push occurred.




## Final verification and live Workbench readback

Complete gate: `scripts/verify_phase5_b.ps1` PASS, exit 0.
Log: `test-results/phase5_b1a-final-gate.log`; JUnit: `test-results/phase5_a.xml`.

| Check | Final result |
| --- | --- |
| Backend regression | PASS — 1,249 tests |
| PostgreSQL/integration including migrations | PASS — 231 tests, included in backend total |
| Frontend regression | PASS — 100 tests across 11 files |
| Ruff / format | PASS — 326 Python files formatted |
| Strict mypy | PASS — 276 source files |
| Secret scan | PASS — 411 project files |
| Frontend typecheck / lint / format / production build | PASS |
| Scope / Git-ignore / frozen lineage | PASS |
| Frozen evidence | PASS — 1,044 files byte-for-byte unchanged |
| Both failed acceptance manifests | PASS — independently reloaded; still failures, not successful results |
| git diff --check | PASS |

Added coverage: 16 backend tests and 1 frontend test. The existing Windows process
escaping test also exercises literal shell metacharacters without shell execution.
The initial gate's secret scanner flagged the deliberately synthetic rejected-password
fixture. Only that known synthetic line was annotated; the final complete gate passed.

After the tested web-service refresh, the real project API reports
Research Environment = BLOCKED_TESTER_CACHE, build 6230 and the selected binding.
Post-refresh checks confirm unchanged project, candidate, authorization history,
saved configuration, both persisted failed attempts and all six failed evidence files.
Before/after API snapshots and the evidence hash inventory are in `.local/phase5_b1a/`.
No additional acceptance attempt or valid BaselineResult was created.

Final decision: stop at the precise cache-layout blocker. Phase 5B.1 is NOT ready
for an acceptance retry. The terminal executable is discovered and pinned, but
native isolated tester initialization has not been proved. Reload the Workbench
Baseline tab to see the Research Environment status. No commit/tag/push was made.
