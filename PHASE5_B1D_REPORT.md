# Phase 5B.1D — Fixed no-trade Expert and native tester initialization

Date: 2026-09-28 (Asia/Bangkok).
Implementation verification: **COMPLETE / PASS**.
Native readiness: **PROCESS_EXITED_DURING_BOOTSTRAP**; not ready for Gold Scalper retry.

## Prerequisites

Before implementation, HEAD, origin/main and `phase5b-tooling-v0.1.6` resolved to
`38e022b8dd70d245500ecfa8ea332a99061f1bd2`; the working tree was clean. All earlier tag
objects and the v0.1.6 object were unchanged. All 1,044 frozen evidence files passed
byte verification. Historical probe hashes, project fields, saved configurations and
the two failed BaselineRuns matched the preserved Phase 5B.1C snapshots.

## Fixed project-owned Expert

Source: `src/trading_ecosystem/tester/probe_expert.mq5`.
Canonical LF source SHA-256:
`5ed1af298c18aabd9223eb7988eb84c79f610289bdb2db925e4a85a68afa62de`.

This fixed source rejects non-tester and optimization contexts, emits a deterministic
initialization marker, emits the first-tick marker once, calls TesterStop and records
deinitialization. It has no inputs, includes, external dependencies, trading-library
imports, broker writes, file/network calls or DLL imports. Source hash verification
precedes compilation. There is no user-source upload, configurable source path or new
execution endpoint. Generated EX5 is Git-ignored and never replaces a user/vendor EA.

Only Git text checkout CRLF-to-LF normalization is applied to the fixed source before
checking its pinned hash and compiling those exact canonical bytes. No claim of
cross-build EX5 reproducibility is made from this single compilation.

## Compiler and artifact identity

Compiler: `C:\Program Files\MetaTrader 5\MetaEditor64.exe`, MetaQuotes Ltd.,
MetaQuotes Language 5 Editor, build **6230**, from the pinned terminal installation.
Compiler SHA-256:
`cf2750bde55d98a1f3b4e56bcdd4f59300d0cff5caa6760985f7ef2c2cc12229`.

The compiler and installed DLLs were copied to a fresh owned portable compiler directory.
The fixed MQ5 was compiled locally with the documented compile/log options; no compiler
was downloaded and no source installation/profile was modified.
Compilation occurred **once**. Native diagnostics reported **0 errors, 0 warnings**, with
624 ms compilation time. MetaEditor returned process exit code **1**.

The first implementation incorrectly required exit code 0 and recorded
PROBE_COMPILATION_FAILED despite a new EX5 and successful diagnostics. Before any tester
launch, the contract was corrected to require an accepted exit code (0 or the observed 1),
positive zero-error/zero-warning diagnostics and a nonempty artifact from the new compile
directory. Original compilation and initial assessment files were preserved; an appended
`compiler/reconciled.json` links their hashes and records the independently checked artifact.
No recompilation or native-probe retry was performed.

Generated EX5: **6,672 bytes**, SHA-256:
`6397dac745a62d7b9bab369b4eb7c48b1fb432b8a3430adacbbcbd742da1f635`.
Both the compiler-output EX5 and isolated staged Expert were independently hash-checked.

The compiler CLI follows the official
[MetaEditor external compiler documentation](https://www.metatrader5.com/en/metaeditor/help/beginning/integration_ide).
The Expert uses the documented normal early-stop mechanism,
[TesterStop](https://www.mql5.com/en/docs/common/testerstop).
TesterStop was not reached in this actual native attempt.

## Exactly one native probe

Probe ID: **b27fb7bd-41e3-41b0-b4f2-84c96f483692**.
Classification: ENVIRONMENT_BOOTSTRAP_PROBE, not BaselineRun/BaselineResult.
Outer observation window: **60 seconds**, registered before compilation/launch; no extension.
Compiler failsafe was independently fixed at 60 seconds. Persisted baseline timeout stays
**600 seconds**.

The probe derived the existing XAUUSDm / M5 / EVERY_TICK_BASED_ON_REAL_TICKS settings,
2026-01-01 through 2026-06-30, 300 USD, leverage 1:100 and TESTER_DEFAULTS. A new internal
Expert UUID was used only in memory/diagnostic files. No persisted configuration was edited.
No Gold Scalper bytes were read or staged for this probe.

| Required observation | Actual result |
|---|---|
| PROCESS_STARTED | Verified root PID 13128, parent PID 25008; pinned terminal image hash |
| Terminal build | 6230 in native terminal journal |
| Native start time | 2026-09-28T08:48:20.859453Z |
| CONFIG_ACCEPTED | Exact Startup event for this probe's bootstrap.ini at local 15:48:24.336 |
| PROBE_EXPERT_LOADED | Not established; staged file presence is insufficient |
| OnInit marker | Not observed |
| First-tick marker | Not observed |
| Tester/agent descendants | None observed |
| TesterStop/deinit | Not observed |
| Native end time | 2026-09-28T08:48:30.772779Z |
| Native exit | 3294954943 unsigned / -1000012353 signed; before timeout |
| Cleanup | Owned root exited; no remaining MT5/compiler process observed |
| Final native classification | PROCESS_EXITED_DURING_BOOTSTRAP |

The native Tester component explicitly reported:
`tester not started because the account is not specified`.
The terminal shutdown message repeated this reason with signed exit code -1000012353.
The missing-EX5 blocker from Phase 5B.1C was not repeated. The current precise blocker is
**TESTER_ACCOUNT_NOT_SPECIFIED** in the isolated environment.

A separate MQL5.community authorization-failed line is not classified as candidate
license denial. No credentials were requested, supplied or copied; no account/profile
configuration was changed to overcome the blocker. No second native probe was attempted.

## Readiness semantics and limitations

Marker matching requires the exact generated Expert component and fresh owned Tester
log source, exact marker messages in sequence, accepted configuration and corroborating
owned tester process identity. A marker from another Expert or unrelated log is rejected.
Init-only evidence can establish TESTER_INITIALIZED while leaving tick capability unknown.
BOOTSTRAP_READY additionally requires first tick, native deinit/normal process exit and
verified cleanup. Successful staging or compilation alone never establishes initialization.

The actual probe reached **CONFIG_ACCEPTED** only. Current XAUUSDm native compatibility,
requested-model execution and full-range real-tick availability remain **UNKNOWN**.
Even a later first tick would not prove complete real-tick coverage for the requested interval.
No model downgrade, trading metric, profitability assessment or normalized result was produced.

The previous 10-second TIMEOUT and Phase 5B.1C missing-EX5 probe remain unchanged historical
evidence. The account requirement shown here is a native tester environment limitation,
not evidence of an EA defect or license restriction.

## Evidence and tests

Ignored evidence: `.local/phase5_b1d/diagnostic/`, including preregistration,
compiler diagnostics and reconciliation, native launch marker, the unique probe runtime,
`native-assessment.json` and byte-hash `files.json`. Previous files were never overwritten.
The original compiler failure assessment is preserved separately from the reconciled
successful compilation and final native result. `native-no-trade-final.json` is a new
Workbench observation file, leaving earlier observations intact.

New tests cover source identity and prohibited APIs, compiler success/unavailable/failure/
timeout/build mismatch, exit-code-1 success diagnostics, binary hashes, exact marker
sequence, init without tick, incorrect marker source/Expert, process/cleanup requirements,
normal stop, isolated staging, no candidate, immutable configuration/history, exclusive
single launch, rejection of arbitrary EX5 paths and account-blocker versus license semantics.
No real MT5 process is launched by the regression tests.

| Final full gate | Result |
|---|---|
| Backend | PASS — 1,290 tests |
| PostgreSQL/integration (included above) | PASS — 231 tests |
| Frontend | PASS — 100 tests / 11 files |
| New no-trade tests | PASS — 20 cases |
| Ruff / format | PASS |
| Strict mypy | PASS — 280 files |
| Secret scan | PASS — 419 project files |
| Frontend typecheck / lint / format / production build | PASS |
| Migrations / scope / Git-ignore / frozen lineage | PASS |
| Frozen evidence | PASS — 1,044 files byte-identical |
| Historical probe/run files | PASS — 968 files byte-identical |
| New diagnostic files | PASS — 492 files independently hash-verified |
| Prior BaselineRuns | PASS — exactly two unchanged failed runs; manifests verified |
| Git diff whitespace | PASS |

Gate log: `test-results/phase5_b1d-final-gate.log`. Independent diagnostic readback:
`.local/phase5_b1d/independent-readback.json`. The refreshed Workbench shows the new
probe ID and PROCESS_EXITED_DURING_BOOTSTRAP. All other project fields, declarations,
saved configurations and historical runs exactly match the before snapshot. Compiler,
terminal and tester processes were absent after execution. No EX5 or runtime data is tracked.

## Changed files

- `src/trading_ecosystem/tester/probe_expert.mq5`
- `src/trading_ecosystem/tester/no_trade.py`
- `src/trading_ecosystem/tester/bootstrap.py`
- `src/trading_ecosystem/tester/environment.py`
- `src/trading_ecosystem/tester/checkpoint.py`
- `scripts/verify_phase5_b_scope.py`
- `tests/test_phase5b_no_trade.py`
- `PHASE5_B1D_REPORT.md`

## Stop, blockers and deviations

Gold Scalper Phase 5B.1 is **not ready for retry**. Native tester initialization requires
an account context that this isolated diagnostic deliberately did not import or configure.
Any next step requires separately scoped authorization; no credentials, existing profile
or live account were used here. No Phase 5C, optimization, external-EA inference, forward
trading, commit, tag or push occurred.

Deviation: the initial compiler exit-code assumption was corrected using actual native
diagnostics and artifact readback, preserving original evidence. Automatic approval review
initially failed at usage limit before executing anything; after the user resumed, one
compilation and exactly one native tester probe were performed. No repeated probing.
