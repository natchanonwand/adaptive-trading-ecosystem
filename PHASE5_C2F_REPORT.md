# Phase 5C.2F — Runtime attestor transport qualification

Status: UNKNOWN_TRANSPORT_FAILURE. RUNTIME_ATTESTATION_TRANSPORT_READY is false.
One authorized RUNTIME_TRANSPORT_QUALIFICATION launch was consumed. No retry is permitted.
Baseline HEAD/origin/main/phase5c-workspaceprobe-v0.1.0: 5d8cf21fb39df7dcef2255756cb69665eb4fcfd8.

## Minimal probe and build

RuntimeTransportProbe.mq5 opens only RuntimeTransportProbe.txt in the normal MQL5 Files sandbox,
immediately writes/flushes STARTED, records schema/script/version/build/data path, then writes and
flushes COMPLETED, closes the file and returns. It has no loops, waits, timers, account/chart/Expert
inspection, trading, network, DLL, globals or chart mutations. No credentials are captured.
Source SHA-256: 36c91fd226921375e5702116f26f85f0af69e8e5324086e486057aa33f898c13.
EX5 SHA-256: cf8bfd67fba0e74eec53ced6326c43e0f66a131c6cf2c4c5de7c003e5df9c98a.
MetaEditor build6230: 0 errors, 0 warnings. No canonical reference source/EX5 or old attestor changed.

Official startup/file semantics used (not treated as runtime proof):
https://www.metatrader5.com/en/terminal/help/start_advanced/start
https://www.mql5.com/en/docs/files/fileopen

## Native evidence

Launch ID: e7ff8b84-383b-436e-95d3-da9514e12c63.
Kind: RUNTIME_TRANSPORT_QUALIFICATION, MAIN_MODE, /profile:Euro, Script=RuntimeTransportProbe,
ShutdownTerminal=1, no StartUp Symbol, no /portable, no Tester section, no credentials.
Existing Euro static attachment safety was rechecked; profile identity/isolation was NOT under test.
Only the separate diagnostic EX5 was exclusively staged in MQL5/Scripts and removed after cleanup.
The startup INI disables Experts/trading/DLL import. No external close request or SDK wait was used.
The existing job ownership guard applied a 45-second timeout; normal terminal exit was not observed.
No terminal/tester process remained after cleanup. No tester was observed.

The native journal states: script RuntimeTransportProbe (EURUSD,Daily) loaded successfully.
This proves a native load attempt was accepted, NOT that OnStart executed. No START/COMPLETE log,
write-failure log or script-return observation was captured. START marker: absent; COMPLETE: absent.
No output file exists at the expected project-owned path:
C:/Users/natch/AppData/Roaming/MetaQuotes/Terminal/D0E8209F77C8CF37AD8BF550E51FF075/MQL5/Files/RuntimeTransportProbe.txt
Actual evidence payload location, file SHA and deterministic payload identity: unavailable.
Only this exact non-FILE_COMMON output path was checked; arbitrary user directories were not scanned.
Known terminal/MQL5 journal deltas were collected through existing sanitization.

Script execution, writing, return and shutdown remain unproven. Do not infer dispatch syntax is wrong,
that a write failed, or that the script hung from the absent payload. Do not classify this as profile
isolation failure. The exact supported category is UNKNOWN_TRANSPORT_FAILURE.
Default and Euro inventories remained byte-identical to this launch's pre-state.

Native evidence manifest: 639cd75262762fe665484533581005efe6b66dff55479af1dfe03c5780f9349f.
Ignored evidence: .local/phase5_c2f/transport-probe.
A narrow offline semantic correction distinguishes native load acceptance from OnStart execution.
The original assessment field startup_script_dispatched recorded loader acceptance; it must NOT be
read as OnStart proof. Its immutable original record was retained. The explicit offline readback
uses startup_script_load_observed=true and onstart_verified=false, preserving the same failure state.
Offline readback manifest: b34a86806f561efa855522c2006ad31ebe56db4728f8cd3dbf23421111ac601f.
No native retry or extra launch occurred for that correction.

## Preservation and scope

Campaign NOT_AUTHORIZED; START disabled; campaign executions0; budget0/11; LOCKED_OOS sealed;
Gold Scalper executions1. No ExperimentRun, EnvironmentQualification, BaselineRun, WorkspaceIdentity,
campaign integration, dry-run, candidate rebuild, prior-evidence mutation or commit/tag/push.
Research tables are compared by deterministic read-only digest against pre-phase state; all prior
tracked source, reports, previous tags and historical evidence are separately hash-verified.

New files (6): this report; scripts/verify_phase5_c2f.py; scripts/verify_phase5_c2f.ps1;
src/trading_ecosystem/tester/RuntimeTransportProbe.mq5; src/trading_ecosystem/tester/transport.py;
tests/test_transport_probe.py. Runtime build/helper/evidence remains ignored under .local/phase5_c2f.

Focused tests: 18 cases for START/COMPLETE semantics, deterministic identity, exact sandbox path,
missing/partial/malformed payload, explicit write/runtime failure, load versus OnStart, completion
versus return/shutdown, forbidden/duplicate fields including credentials and volatile timestamps,
wrong data root/build, no filesystem/research mutation, no profile-isolation conclusion, prohibited
MQL operations, and unexpected tester blocking. Persisted budget/ExperimentRun invariance is also
checked by the phase verifier before/after the full gate.

Full gate: pending at report creation; final result will be appended after completion.
Workspace attestation is NOT qualified for retry by this outcome. Any later diagnostic/native
continuation needs separate authorization; no workspace isolation or START readiness is derived.
Deviation: no scope deviation. The explicit offline naming correction is documented above.

## Final gate completion — 2026-10-17

Full applicable verification: PASS. This is a regression/preservation PASS, not transport readiness.
The interrupted full-gate.log was preserved. No completed gate was inferred from that partial log.
full-gate-resumed.log records 1,597 backend tests PASS in 360.37s, including314 PostgreSQL/integration
and migration cases; Ruff PASS; format416 files PASS; strict mypy342 source files PASS.
The gate stopped on a detect-secrets false positive in the public diagnostic protocol test fixture.
A narrowly documented inline allowlist and line wrapping changed comments/string layout only, with
identical payload bytes and executable behavior. The first annotation exceeded the Ruff line limit;
full-gate-completion.log preserves that failure. No frozen scanner or gate was changed.
full-gate-completion-2.log records successful remaining checks: Ruff/format, secret scan, registry,
frontend typecheck/lint/format, frontend178 tests, production build, scope/ignore/lineage, frozen and
historical evidence, prior Phase5B run-manifest readback, Phase5C/source/UI preservation, and diffcheck.
Passing backend/mypy were not unnecessarily rerun after the comment-only fixture correction.

The existing local PostgreSQL cluster was started without reset after the interruption. The initial
wrapper stopped before tests on a stale shell exit code; direct pg_ctl status then confirmed it was
running. Preservation passed before and after the resumed gate. The previously blocked read-only
manifest check (automatic approval review unavailable due to usage limit) completed successfully.
Offline readback manifest/files independently verified; canonical reference source and EX5 remain
covered by before/after hashes. Frozen1044/historical1621 and all research rows remain unchanged.

Final outcome: UNKNOWN_TRANSPORT_FAILURE; transport ready=false. Native launch count for this phase
remains exactly1. No additional native operation occurred during resume. No START/COMPLETE payload,
no payload file identity, no verified OnStart/return/shutdown. Workspace isolation NOT_ASSESSED.
No retry, WorkspaceIdentity, campaign integration/dry-run, START authorization, OOS access, Gold
execution, commit/tag/push. Campaign NOT_AUTHORIZED; START disabled; executions0; budget0/11;
OOS sealed; Gold executions1. Any further native diagnostic requires separate authorization; the
workspace attestor must not be retried on an assumption that transport is ready.
