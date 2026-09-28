# Phase 5B.1C — Native tester handshake, observability and readiness

Date: 2026-09-28 (Asia/Bangkok).

Implementation verification: **COMPLETE / PASS**.
Native outcome: **PROCESS_EXITED_DURING_BOOTSTRAP**, not BOOTSTRAP_READY.
Gold Scalper acceptance must **not** be retried under this authorization.

## Baseline and preservation

HEAD, origin/main and frozen `phase5b-tooling-v0.1.5` resolved to
`bd5780b59068f6dd81d2bb55cc748dbf978658e8` before implementation. Working tree was
clean. Existing scope/lineage and 1,044 frozen-evidence checks passed before changes.
All historical tags, Phase 5B.1B source checkpoint and reports remain intact.

The previous probe `cb6a9d86-da1a-4f07-b2d3-89c32e35695a` retains its original
10-second TIMEOUT and assessment. That observation is **inconclusive for tester
readiness**: it proves neither EA initialization failure, license/tester denial,
symbol incompatibility nor unavailable real ticks. No historical diagnostic was rewritten.

## Readiness evidence contract

Ordered stages are PROCESS_NOT_STARTED → PROCESS_STARTED → CONFIG_ACCEPTED →
TESTER_SUBSYSTEM_STARTING → TESTER_INITIALIZED → BOOTSTRAP_READY. Stages are
derived deterministically from corroborated evidence, not elapsed time alone.

- PROCESS_STARTED requires an observed owned root process with the expected executable
  path/identity. Windows process snapshots identify parent/child relationships; native
  handles retain exit status and process times through cleanup.
- CONFIG_ACCEPTED requires the exact Startup-component event referencing this probe's
  absolute INI path in its newly owned terminal log. A different path or vague substring
  does not qualify.
- TESTER_SUBSYSTEM_STARTING additionally requires an owned descendant tester process
  whose image path resolves to the staged tester executable. A name alone is insufficient.
- TESTER_INITIALIZED additionally requires the ordered agent startup/build, loopback
  server-start and completed-initialization events in the **same fresh Tester log**.
  Their components and complete message patterns must match. Agent build must match the
  pinned build. Terminal startup is not this event.
- BOOTSTRAP_READY also requires observed process cleanup. Native readiness never implies
  candidate acceptance, symbol/history compatibility, real ticks or successful strategy results.

The agent-log contract is grounded in the official
[MetaTrader Journal of Testing documentation](https://www.metatrader5.com/en/terminal/help/algotrading/tester_journal).
Unknown/new native message formats remain unverified rather than matching loosely.
Positive tester-handshake patterns are covered synthetically but were **not observed on
the real build in this phase**, so their practical applicability remains unqualified.

Other classifications include PROCESS_START_FAILED, CONFIG_REJECTED,
PROCESS_EXITED_DURING_BOOTSTRAP, BOOTSTRAP_TIMEOUT and BOOTSTRAP_INDETERMINATE.
The config-rejection pattern is conservative and has no claimed real observation here.
Corroborated initialization or unexpected test-start progress causes cancellation;
the Windows kill-on-close job bounds the entire owned process tree. No auto-extension.

## One preregistered probe

New probe: **b083af2a-0e94-4400-ab27-525540b22d66**.

The observation limit was fixed at **45 seconds before launch**. Exclusive creation of
`preregistration.json` prevents an interrupted or repeated invocation from launching again
under the same phase root. It is an environment observation limit, not a strategy parameter.
The persisted baseline timeout remains **600 seconds**.

Same pinned MetaQuotes terminal build **6230**, terminal binding
`0b14ea86-61b9-4f0f-b9dd-ac766c6166df`, and source profile were used. Source profile,
accounts and cache were not staged or mutated. Executable SHA-256:
`602b2f42f2219a9d33ddcb3d935d85fddd92033d9eaccc5fea3f2285b389ce44`.
The probe used a fresh portable runtime and an intentionally absent UUID Expert,
preserving all existing XAUUSDm/M5/model/date/deposit/leverage/input parameters.
No Gold Scalper binary was staged or executed, and no BaselineRun/BaselineResult was created.

| Observation | Actual evidence |
|---|---|
| Root process | PID 29236, parent PID 20052; pinned image verified |
| Native creation time | 2026-09-28T04:17:35.769205Z |
| End first observed | 2026-09-28T04:17:49.833485Z |
| Exact native exit FILETIME | Unavailable/null; observation time is retained separately |
| Native exit code | 3294954941 unsigned / -1000012355 signed |
| Config acceptance | Exact Startup event at native local time 11:17:40.014 |
| Tester/agent descendants | None observed |
| Tester initialization | Not established |
| Stage reached | CONFIG_ACCEPTED |
| Timeout | False; native exit occurred before the 45-second limit |
| Cleanup | Verified from owned process exit observation |
| Final classification | PROCESS_EXITED_DURING_BOOTSTRAP |

The terminal and tester journals reported the intentionally absent Expert:
`Experts\2c4413d63cb64c07933756374cc35226.ex5 not found`.
The terminal then recorded that the tester did not start and shut down with signed code
-1000012355, identified by MT5 as `tester EX5 not found`. This establishes a concrete
reason for **this non-candidate probe's** early exit. It does not establish a defective
Gold Scalper EA, license denial, tester-access denial or broker/symbol incompatibility.

No second probe was attempted. No inert/helper EA was introduced to force initialization,
and no candidate run was used to answer environment-readiness questions.

## Evidence, diagnostics and limitations

Git-ignored evidence root: `.local/phase5_b1c/`.

- `handshake/preregistration.json`: fixed window, binding and no-candidate scope.
- `handshake/probes/<probe-id>/`: generated INI, fresh native logs, original probe result.
- `handshake/assessment.json`: exact source-relative log locations, native log times,
  capture timestamps, process identities/times/codes and deterministic stage classification.
- `handshake/files.json`: byte hashes for independent readback.
- `preserved-before.json` / `preservation-after.json`: previous probe/run preservation.
- `.local/phase5_b/native-handshake.json`: a new observation file; the prior
  `native-bootstrap.json` TIMEOUT is untouched.

Only logs from this newly generated runtime are inspected. Diagnostic sanitization removes
credential-like lines and account/login identifiers before persisting derived observations.
Safe native logs retain their original bytes; sensitive native lines, if present, are
redacted only in the newly owned runtime. No secrets are copied from the source profile.

Process ancestry is sampled at 250 ms intervals. Extremely short-lived descendants may
escape observation; absence of an observed child is not proof that none existed momentarily.
This limitation cannot produce READY because positive corroboration is mandatory.
Exact native root exit time was unavailable, while its observed end time and exit code
were captured. Unknown state is preserved rather than fabricated.

Prior read-only recognition of **XAUUSDm** remains known historical evidence.
Current native tester symbol compatibility, requested history and full-interval
real-tick readiness remain **UNKNOWN**. The model was not downgraded.

## Tests and gate

New synthetic and harmless-process tests cover stage order, process-without-signal,
config acceptance, corroborated tester initialization, wrong build/source/config/order,
child identity without corroboration, logs without root process evidence, process exit,
config rejection, missing cleanup, fixed exclusive preregistration, preservation of the
old TIMEOUT, no candidate/result creation, sanitization and native PID/parent/times/exit
observation. Existing broker-write, optimization and process-tree checks remain active.
Workbench tests verify the new last-probe display and disabled candidate-run control.
Focused new suite: **18 passed**.

| Full gate | Result |
|---|---|
| Backend | PASS — 1,270 tests |
| PostgreSQL/integration (included above) | PASS — 231 tests |
| Frontend | PASS — 100 tests / 11 files |
| Ruff / formatting | PASS |
| Strict mypy | PASS — 278 files |
| Secret scan | PASS — 415 project files |
| Frontend typecheck / lint / format / build | PASS |
| Migrations / scope / ignore / frozen lineage | PASS |
| Frozen evidence | PASS — 1,044 byte-identical files |
| Prior probe/run preservation | PASS — 484 files byte-identical |
| New probe independent hash readback | PASS — 482 files |
| Historical BaselineRuns | PASS — exactly two unchanged failed attempts |
| Git diff whitespace | PASS |

Full log: `test-results/phase5_b1c-final-gate.log`. Independent readback:
`.local/phase5_b1c/independent-readback.json`. No surviving terminal/tester process was
found after the probe. The refreshed Workbench API reports the new probe ID and
PROCESS_EXITED_DURING_BOOTSTRAP. All other project fields, saved configurations,
declarations and historical run records exactly match the before snapshot.

## Changed files

- `src/trading_ecosystem/tester/handshake.py`
- `src/trading_ecosystem/tester/process.py`
- `src/trading_ecosystem/tester/bootstrap.py`
- `src/trading_ecosystem/tester/environment.py`
- `src/trading_ecosystem/tester/checkpoint.py`
- `scripts/verify_phase5_b_scope.py`
- `tests/test_phase5b_handshake.py`
- `dashboard/src/workbench/ReadinessPanel.tsx`
- `dashboard/src/workbench/api.ts`
- `dashboard/tests/readiness.test.tsx`
- `PHASE5_B1C_REPORT.md`

## Stop and remaining work

Native tester readiness remains unproven. The safe missing-Expert probe cannot get past
MT5's explicit requirement for the referenced EX5 in this observed configuration.
Any further method for non-candidate handshake validation needs a separately authorized
scope; this phase does not retry or select a different strategy.

No commit/tag/push, Gold Scalper retry, BaselineConfiguration change, optimization,
Phase 5C, strategy inference or forward trading occurred. There was exactly one native
environment probe. Its early native exit was observed, not a timeout extension or deviation.
