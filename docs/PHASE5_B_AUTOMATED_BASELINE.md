# Phase 5B — Automated MT5 Strategy Tester baseline

Immediate baseline: `phase5a-v0.1.1` (`e83c41b`). The original
`phase5a-v0.1.0` (`ec87ad2`) and all older research evidence remain frozen.
This phase enables one explicitly confirmed tester configuration per run. It
does not enable broker trading, optimization, scoring, or behavior inference.

## Workbench flow

Open a registered project → Baseline → enter a historical interval, deposit,
leverage, timeout and input provenance → Run Baseline → review the persisted
configuration and identities → confirm authorized tester use → start.
Creating/reviewing a configuration does not execute it. The broker symbol and
timeframe come from the project's explicit Phase 5A binding.

The page displays the actual persisted state, elapsed wall time and cancellation.
It does not estimate a percentage. Completed results include normalized metrics,
unavailable fields, report/result hashes and the evidence manifest identity.
Failures have actionable descriptions. Opening a saved run reloads its persisted
configuration/result; it does not run it again. Configuring another attempt
creates another UUID and requires another explicit confirmation.

## Operator setup

The existing local PostgreSQL database and installed MT5 binaries are prerequisites.
Run the existing core and Workbench migrations, followed by:

```powershell
.venv/Scripts/python.exe -m alembic -c alembic-baseline.ini upgrade head
```

Supply `TE_DATABASE_URL` through the existing protected runtime setup; never place
it in reports. The additive `workbench.baseline_alembic_version` lineage is
independent of the frozen Workbench `0001_projects` lineage. It adds
`workbench.baseline_runs` and `workbench.baseline_results`, with foreign keys to
the project and run. Destructive downgrade is rejected.

Create the Git-ignored `.local/phase5_b/environment.json` with these operator
fields (no account credentials):

| Field | Meaning |
|---|---|
| `terminal_executable` | Absolute path to the project's trusted installed `terminal64.exe` |
| `terminal_sha256` | Lowercase SHA-256 of that installed executable |
| `cache_directory` | Absolute MT5 `Bases` directory containing the selected server |
| `broker_name` | Exact project broker name |
| `server` | Explicit server directory name, restricted to letters/digits/dot/dash/underscore |
| `terminal_build` | Operator-declared build number; not an observed native result |

Only operator-controlled local configuration selects executable/cache paths.
They cannot be supplied through a browser API. Start the existing entry point:

```powershell
.venv/Scripts/python.exe -m trading_ecosystem.workbench --port 8785
```

The Phase 5B server binds only to loopback, retains Phase 5A onboarding endpoints,
and adds same-origin baseline routes. An unmodified Phase 5A server remains
compatible with the frontend and retains its original unavailable placeholder.
Users do not operate MT5 or PowerShell for each baseline; operator provisioning
is required once before eligible execution.

## Supported configuration

- Environment: `DEMO_RESEARCH_TESTER`; no broker account execution.
- Explicit supported symbols: `XAUUSDm`, `BTCUSDm`, `USTECm`, matching the project.
- Timeframes: M1, M5, M15, M30, H1, H4, D1, matching the project.
- Historical interval from 2000 onward, ending no later than today's UTC date;
  1–366 days. The MT5 date-only end boundary is exclusive.
- Positive USD deposit up to 100,000,000, at most two decimal places; leverage
  1–2000. These are tester accounting settings, not Risk Engine policy changes.
- Process timeout 30–3600 seconds. Staging has a separate maximum 120-second
  loop deadline and 2 GiB copy budget; an individual OS file copy is not preempted.
- Model is always `Model=4`, Every tick based on real ticks. There is no downgrade.
- Inputs are either opaque binary defaults in a fresh profile or explicit `.set`
  contents (maximum 65,536 characters) with SHA-256. No cached prior `.set` is
  copied. Optimization-enabled rows and credential-like content are rejected.
  This is not automatic extraction of undocumented binary defaults.

## Adapter and process ownership

The adapter verifies the registered EX5, the operator-pinned terminal hash, exact
broker binding and matching cached history/tick folders. It creates a fresh
portable directory under the run evidence root. It copies terminal/tester root
binaries, root DLL dependencies, the exact symbol's `.hcc`/`.hcs`/`.tkc` cache,
and `symbols.raw`. It never copies source account settings, profiles, charts,
other EA files or licensing material. All staged runtime file hashes are recorded.
EX5 bytes are opaque and copied unchanged to an internal UUID filename.

The generated INI disables live expert trading and DLL imports, clears startup
expert/script, requests a single test with optimization/forward/cloud/remote
testing disabled, refuses report replacement and requests terminal shutdown.
Native CLI/configuration switches follow the
[official MT5 startup documentation](https://www.metatrader5.com/en/terminal/help/start_advanced/start).

Windows `CreateProcessW` receives an explicit executable and structured argument
list, with no shell. A suspended process is assigned to an owned kill-on-close
Job Object before it can run. Its window is hidden. Timeout, cancellation and
root exit close that job and terminate its descendants, without enumerating or
killing unrelated terminals. Only minimal Windows environment variables are
inherited; application/database secrets are excluded.

A Windows file lock serializes workers using the canonical `.local/phase5_b`
root. Busy starts are rejected; no automatic queue/retry is hidden. Separate
roots still use separate portable directories and never share writable terminal
profiles/caches. On restart a free ownership lock allows abandoned active states
to become `TESTER_FAILED / INTERRUPTED_OWNER`; partial evidence remains untouched.
An interrupted run cannot be resumed or restarted using its existing UUID.

## States, declarations and acceptance of a result

Normal path: READY → QUEUED → PREPARING → RUNNING → PARSING → COMPLETE.
NOT_READY is the project/configuration readiness boundary. Typed terminal states:
BLOCKED_LICENSE, BLOCKED_TESTER_ACCESS, BLOCKED_SYMBOL,
BLOCKED_ARTIFACT_IDENTITY_MISMATCH, BLOCKED_REAL_TICKS_UNAVAILABLE,
INITIALIZATION_FAILED, TESTER_FAILED, TIMEOUT, REPORT_MISSING,
REPORT_PARSE_FAILED, CANCELLED. Terminal states cannot transition to another run.

Declared license/tester access are snapshots of the user's statements; observed
execution status is separate. UNKNOWN means not yet verified and does not block
readiness or preflight by itself. Explicit NOT_AUTHORIZED/UNAVAILABLE declarations
block their respective license/tester-access paths. Known native
license/tester/init failures become typed failures; unfamiliar failures remain
generic or unavailable rather than being guessed. Observed tester denial records
TESTER_ACCESS_BLOCKED separately from LICENSE_BLOCKED; neither changes declarations.
Current list/detail readiness is derived from declarations, binding and artifact
verification without rewriting old stored project history or run evidence.

`Model=4` is insufficient evidence of fidelity. Current qualification requires
native log text reporting `100% real ticks`, with no lower percentages or known
fallback indicators. Missing/unknown evidence blocks completion. The report must
match the staged Expert UUID, exact symbol, timeframe, start/end dates, deposit
and leverage; currency/model are checked when exposed. A nonzero exit, missing
report or validation failure cannot produce a database BaselineResult.

## Parser and evidence

The parser uses Python's HTML parser, not OCR or browser execution. UTF-8 and
BOM-marked UTF-16 English MT5 HTML layouts are supported. Known labels must be
unique. Numeric values accept a decimal point with validated comma/space thousands
grouping. Ambiguous decimal commas, malformed durations/drawdowns and inconsistent
trade counts fail closed. The checked-in report is hand-authored synthetic test
data shaped like an MT5 report; it is not real acceptance evidence.

Available normalized fields: initial deposit, net/gross profit and loss, profit
factor, expected payoff, maximal balance/equity drawdown, total/winning/losing and
long/short trades, win rate (fraction 0–1), largest/average profit/loss trades,
maximum consecutive wins/losses, average/maximum holding duration. Missing
metrics are `null` and named in `unavailable`; the UI shows UNAVAILABLE. Zero
trades does not imply a zero win rate. Drawdowns preserve normalized amount and
percentage; holding times use validated `hours:minutes:seconds` strings.

Report metadata includes Expert, Symbol, Period, parsed interval/timeframe,
Model, History Quality, Build, Leverage, Currency, Company and Ticks, each with
explicit UNAVAILABLE semantics. Operator build metadata is labeled separately.

Evidence lives under `.local/phase5_b/runs/<project-id>/<run-id>/`:
immutable configuration snapshot, tester.ini, staged identities, sanitized log,
raw report (when produced), normalized result, execution/failure metadata, and a
SHA-256 manifest. The runtime directory retains copied caches/binaries and partial
native output. No EA binary is tracked in Git. Reports are never served as HTML.
Credential-like native log lines are redacted; a report containing credential-like
content is quarantined by redaction and rejected, retaining its pre-redaction hash
and reason instead of retaining private bytes. Normal accepted reports remain raw.

Completion independently reparses the saved report before database acceptance.
`scripts/verify_phase5_b_evidence.py` independently reloads finalized manifests
and results. Hash identities establish byte linkage, not a vendor signature or
proof that a malicious EA's statements are truthful. Missing/partial manifests
are not accepted by the final evidence gate.

## API

| Method / path under `/workbench-api` | Purpose |
|---|---|
| POST `/baselines` | Persist an immutable configuration; identical UUID retry is idempotent |
| GET `/baselines?project_id=<uuid>` | List at most 100 saved runs for a project |
| GET `/baselines/<uuid>` | Persisted run plus result, if complete |
| POST `/baselines/<uuid>/start` | Explicit `confirmed: true`; reject busy/finalized runs |
| POST `/baselines/<uuid>/cancel` | Explicit cancellation of a ready or owned active run |

Write requests require the existing local Host/Origin/fetch-site checks and
`X-Workbench-Request: 1`. Request bodies, timeouts and IDs are bounded. Error
responses do not echo input values. There is no generic command/path endpoint.

## Verification and limitations

Run `scripts/verify_phase5_b.ps1` with the existing dedicated local PostgreSQL
test administrator URL. It calls the unchanged Phase 5A complete regression gate,
plus Phase 5B scope and evidence checks. All previous tests remain intact. Scope
originally allowed three existing integration files to change. The Phase 5B.0.1
readiness correction additionally permits the three Workbench readiness/API modules
and their existing integration test, while pinning the frozen Phase 5B checkpoint
and an exact correction-file allowlist. It verifies the other 363 Phase 5A
snapshot files byte-for-byte, both Phase 5A commits, prior evidence,
no tracked EA binaries, ignored runtime artifacts and tester-only settings.

The isolated portable/offline cache mechanism has not been qualified with a real
external EA unless a separately recorded acceptance run says otherwise. Some
broker cache layouts, terminal dependencies, data ranges, Marketplace activation,
DLL-requiring EAs and localized reports may be unsupported and must block/fail;
credentials/activation files are not copied to make them work. No data downloading
or automatic terminal provisioning is performed. Job Objects provide process
ownership, not a general hostile-binary sandbox. Only trusted, authorized artifacts
should be registered. A real run remains subject to actual native initialization,
licensing, symbol availability and fidelity verification.

Exactly one real acceptance attempt is permitted after the code gate when an
authorized compatible registered candidate exists. Otherwise report
`BLOCKED_NO_AUTHORIZED_CANDIDATE`. Synthetic test results never satisfy real
acceptance. Stop after Phase 5B; no commit, tag, push or Phase 5C is included.
