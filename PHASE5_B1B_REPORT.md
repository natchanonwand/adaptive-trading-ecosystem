# Phase 5B.1B — MT5 cache compatibility and native bootstrap validation

Date: 2026-09-28 (Asia/Bangkok).

Implementation verification: **COMPLETE / PASS**. Native acceptance: **BLOCKED / TIMEOUT**.
Gold Scalper retry is **not ready**. No new BaselineRun or BaselineResult was created.

## Frozen prerequisite

The immediate baseline is `phase5b-tooling-v0.1.4`, commit
`3ad73e72821026da91254100f065f37a390b015e`. HEAD equalled this commit,
the annotated tag resolved correctly, ancestry passed and the working tree was clean
before implementation. The unchanged prerequisite Phase 5B gate passed: 1,249 backend
tests, 100 frontend tests, quality/migration/scope checks and all 1,044 frozen evidence
files. Log: `test-results/phase5_b1b-prerequisite-gate.log` (ignored).
The older tag in the attached specification is superseded by the user's explicit v0.1.4
authorization. No tag, commit or remote ref is changed in this phase.

## Correction and safety contract

The old preflight required `symbols.raw`, `history/*.hcc` and `ticks/*.tkc` and the
adapter copied that assumed cache layout. None proves current symbol/history/model
capability. Those dependencies and source-cache copying are removed. No binary cache
is parsed, renamed, synthesized, purged or copied into a substitute filename.

Binding checks require an absolute non-reparse executable/profile path, the pinned
terminal hash, a unique matching `origin.txt` installation mapping and tester binary.
Generated directories use a new UUID under the owned ignored probe root; report/config
writeability is checked there. Source terminal profiles and accounts are never staged.

Read-only discovery observations retain their historical scope. Native startup is
separate from native tester initialization and from real-tick availability. No filename,
successful process creation or terminal startup sets READY. The production environment
loader remains fail-closed, including legacy environment JSON; the observed TIMEOUT is
surfaced instead of treating a valid binding as candidate execution readiness.
There is deliberately no successful native-profile promotion path in this checkpoint.

## Identity and symbol

- Executable: `C:\Program Files\MetaTrader 5\terminal64.exe`.
- Company/product: MetaQuotes Ltd. / MetaTrader 5 Client Terminal; build **6230**.
- SHA-256: `602b2f42f2219a9d33ddcb3d935d85fddd92033d9eaccc5fea3f2285b389ce44`.
- Profile: `C:\Users\natch\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075`.
- Binding ID: `0b14ea86-61b9-4f0f-b9dd-ac766c6166df`.
- Installation/profile association verified via the existing origin mapping; current
  executable version metadata matches the pinned binding.
- Sanitized prior read-only discovery identifies Exness demo server `Exness-MT5Trial14`
  and exact symbol `XAUUSDm`, observed 2026-09-21T17:51:59.737937Z. Its instrument
  assessment was PARTIAL; exact symbol metadata is present. This is historical symbol
  resolution, not current sizing eligibility or native portable-profile compatibility.
- Current symbol resolution, broker connection, requested history and real ticks remain
  **UNKNOWN**. No suffix substitution or automatic model downgrade occurred. No SDK
  autodiscovery was used to launch the user's existing terminal/account profile.

## Configuration and the one native probe

Persisted configuration `4a6d8cc7-59ef-474e-8eff-feec6d1658de` remains unchanged:
XAUUSDm / M5 / EVERY_TICK_BASED_ON_REAL_TICKS / 2026-01-01 through 2026-06-30 /
300 USD / leverage 1:100 / TESTER_DEFAULTS / 600 seconds. The other pre-existing
saved configuration also remains unchanged.

Exactly one **ENVIRONMENT_BOOTSTRAP_PROBE** was launched:
`cb6a9d86-da1a-4f07-b2d3-89c32e35695a`.
Evidence: `.local/phase5_b1b/` (Git-ignored).

| Observation | Result |
|---|---|
| Process creation | PASS |
| Pinned executable and native build | PASS; 6230 also observed in terminal log |
| Generated INI validation | PASS; research values preserved, optimization/remote/cloud/forward disabled |
| Native start-config acceptance | OBSERVED in terminal startup log |
| Owned runtime/config/output writeability | PASS |
| Native tester initialization | UNKNOWN; not established within probe bound |
| Process lifecycle | Bounded 10 seconds; kill-on-close process job; no surviving MT5 process observed |
| Candidate strategy | Not staged or intentionally executed |
| BaselineRun / BaselineResult | Neither created |
| History / real ticks | UNKNOWN |

INI SHA-256: `dd861b41d989eb75e84125e4de02c884582c7e9922ef78469c87f773968b1885`.
The disposable runtime had no candidate or account/profile/cache copy. Its Tester Expert
UUID intentionally referenced an absent candidate. MT5 itself extracted built-in MQL5
resources on startup; these are ignored runtime artifacts, not user EA uploads.
The probe's 10-second safety bound does not change the persisted 600-second baseline timeout.

Observed remaining blocker: **TIMEOUT — native tester initialization not verified within
the probe bound**. This is not proof of missing cache, missing real ticks, license denial
or tester prohibition. The absence of a candidate/profile limits what this safe probe can
establish; no second probe or baseline retry was attempted to overcome that limit.

Independent readback retained the original `probe.json` and native logs. Its diagnostic
hash originally covered decoded log text before Windows newline translation rather than
the written diagnostic file. The original text digest was reconstructed from native logs
and matched; the exact Windows transformation was checked. An append-only
`probe-assessment.json` records the actual file hash and distinction. Code now hashes the
written diagnostic bytes, with regression coverage. `probe-files.json` records runtime
file hashes. No original probe evidence was rewritten.

## Tests and verification

Updated tests cover arbitrary symbol-cache layout, no-cache binding validation, exact
origin association, missing executable/tester, historical exact-symbol resolution and
unavailability, server mismatch, safe directory failure, exact INI validation, process
start failure/exit/timeout, source-byte preservation, no cache copy, no candidate/result,
native-startup versus tester readiness, diagnostic byte hashes and rejection of forged
READY observations. Existing broker-write/optimization/process-tree boundaries remain.
Workbench regression checks the independently displayed bootstrap blocker and disabled
Run Baseline control. Focused tester/readiness suite: **96 passed**.

| Final gate | Result |
|---|---|
| Backend regression | PASS — 1,252 tests |
| PostgreSQL/integration (included above) | PASS — 231 tests |
| Frontend regression | PASS — 100 tests, 11 files |
| Ruff / format | PASS |
| Strict mypy | PASS — 276 source files |
| Secret scan | PASS — 412 project files, no findings |
| Frontend typecheck / lint / format / production build | PASS |
| Migrations / scope / Git-ignore / frozen lineage | PASS |
| Frozen evidence | PASS — 1,044 byte-identical files |
| Historical failed runs | PASS — 2 manifests and all 6 evidence files unchanged |
| Git diff whitespace | PASS |

Full log: `test-results/phase5_b1b-final-gate.log` (ignored). Independent final readback
also verified all **472** generated probe files against `probe-files.json`. The refreshed
Workbench API reports **TIMEOUT**. All other project fields, authorization declarations,
saved configurations and the two historical run records exactly match the before snapshot.
Final readback: `.local/phase5_b1b/final-preservation.json`. No candidate EX5 matching the
configured Tester Expert exists in the probe runtime.

## Changed source/report files

- `src/trading_ecosystem/tester/adapter.py`
- `src/trading_ecosystem/tester/bootstrap.py`
- `src/trading_ecosystem/tester/checkpoint.py`
- `src/trading_ecosystem/tester/environment.py`
- `scripts/verify_phase5_b_scope.py`
- `tests/test_phase5b.py`
- `tests/test_phase5b_environment.py`
- `dashboard/src/workbench/ReadinessPanel.tsx`
- `dashboard/src/workbench/api.ts`
- `dashboard/tests/readiness.test.tsx`
- `PHASE5_B1B_REPORT.md`

Ignored generated files are confined to `.local/phase5_b1b/`, the new fail-closed
`.local/phase5_b/native-bootstrap.json` observation, normal test output and frontend build
output. Earlier acceptance/calibration reports and failed-run evidence are preserved.

## Scope limitations and deviations

No Gold Scalper retry, candidate optimization, broker writes, Phase 5C, commit, tag or
push. License/tester declarations remain UNKNOWN; no license conclusion is inferred.
Native tester acceptance has not succeeded. Current broker/symbol/history compatibility
needs further separately authorized work; this checkpoint must not enable a real retry.
The diagnostic newline/hash issue and append-only readback correction above are the
only execution-evidence deviation. No probe was repeated.
