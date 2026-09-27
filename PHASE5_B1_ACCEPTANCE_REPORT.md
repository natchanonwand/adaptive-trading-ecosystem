# Phase 5B.1 — Real external EA baseline acceptance

Date: 2026-09-27.

**Status: STOPPED — PREREQUISITE_GATE_FAILED. No acceptance execution occurred.**
This is a pre-execution stop, not a Strategy Tester outcome. No BaselineRun,
acceptance campaign, native tester process or normalized result was created.

## Required baseline and gate

Before the gate, the working tree was clean. HEAD, local origin/main and
`phase5b-tooling-v0.1.1^{commit}` all resolved to:

`a76d896ac031c85951b300d6fa946b93f084ab70`

The unchanged `scripts/verify_phase5_b.ps1` was invoked once. It exited with
code 1 at its initial scope verification:

```text
ValueError: FROZEN_CHECKPOINT_CHANGED: HEAD
Phase 5B scope or frozen checkpoint failed
```

Evidence: `test-results/phase5_b1-prerequisite-gate.log` (Git-ignored).

The scope verifier still pins CHECKPOINT to
`3a35373a7d022fe61a7289a18c33243a8f8fb178` and checks the v0.1.0 tag,
HEAD and origin/main against that older commit. The requested v0.1.1 checkpoint
is therefore rejected even though HEAD matches the newly required tag.
This identifies a stale verification checkpoint; it does not establish that
frozen research evidence was modified.

The authorization explicitly requires STOP if any prerequisite fails. No
verifier, source, tests, tag or evidence was altered to force PASS. Further
execution prerequisites and the acceptance workflow were not continued.

## Candidate and Workbench observations

Read-only API inspection before the gate returned:

| Field | Observed value |
|---|---|
| Project | Gold Scalper PRO Acceptance |
| Project ID | `1b55ae30-d498-4e75-aa4e-74fb97bf62e9` |
| Candidate | Gold Scalper for MT5 EA |
| Candidate ID | `d5508913-c5d6-4f97-99e2-0be7e859b84a` |
| Artifact ID | `a8d06843-bb35-4471-9b46-66746cda30cf` |
| Registered filename | `Gold Scalper for MT5 EA.ex5` |
| Registered SHA-256 | `ea21fcd96c9c5683aaf39fc20cf91cc29234f72ac22f202f726fe30e9d028ce4` |
| Artifact verification returned by API | VERIFIED |
| Project / baseline readiness | BASELINE_READY / READY |
| Canonical asset / broker symbol | XAUUSD / XAUUSDm |
| Broker / environment / timeframe | Exness / DEMO / M5 |
| Declared license | UNKNOWN |
| Declared tester access | UNKNOWN |
| Registered source reference | UNKNOWN |
| Existing BaselineRun records returned by API | None |

The product represents the candidate as a registered EX5 upload
(`USER_SUPPLIED_EX5` representation). Its original acquisition provenance,
authorization and whether it originated from a protected installed Marketplace
artifact are not established by that representation. No protected installation
was inspected, extracted or copied during this task.

Authorization provenance remains **NOT ESTABLISHED** from the available metadata.
The user's authorization is conditional on legitimate acquisition and permitted
tester use; file existence and a VERIFIED hash do not establish those rights.
UNKNOWN declarations remain UNKNOWN and were not reclassified as blocked.

## Configuration and execution

There is no persisted existing BaselineRun configuration in the API response.
XAUUSDm and M5 are explicit project bindings; Every tick based on real ticks is
the required model in the authorization. Dates, deposit, currency, leverage,
timeout and input configuration were not selected or persisted for this campaign.
UI defaults were not treated as an explicitly approved configuration.

| Acceptance item | Result |
|---|---|
| Baseline run / campaign ID | NOT CREATED |
| Exact executed configuration | NONE — execution was not reached |
| Input/set identity and provenance | NOT ESTABLISHED for a run |
| Observed tester status | UNKNOWN — no tester observation |
| Terminal/tester build, process identity | NOT COLLECTED |
| Execution start / end / exit code | NOT APPLICABLE; prerequisite gate exit code is 1 |
| Tester execution result | NOT RUN |
| Normalized metrics | UNAVAILABLE |
| Raw tester report identity | UNAVAILABLE — no report generated |
| Normalized result identity | UNAVAILABLE — no result generated |
| Deterministic report/result readback | NOT RUN |
| Workbench acceptance | Readiness/identity GETs succeeded; end-to-end execution/result display NOT TESTED |

## Regression, preservation and limitations

The mandatory pre-execution gate failed before backend/PostgreSQL/frontend tests,
quality checks and the 1,044-file frozen-evidence audit were reached. Previous
gate results are not substituted for the required current PASS. Byte-for-byte
preservation of all 1,044 files is therefore **not requalified by this attempt**;
none of those files was modified by this task.

Post-acceptance regression was not run because no acceptance attempt took place.
The gate must first be reconciled to the authorized v0.1.1 frozen checkpoint in
a separately authorized correction, preserving strict evidence verification.
Legal/source provenance and an explicit persisted baseline configuration also
remain unresolved before execution can be considered.

Only this requested report and the ignored prerequisite-gate log were created.
There was no EA/MT5 execution, retry, optimization, parameter search, licensing
workaround, binary modification, Phase 5C work, commit, tag or push.

Deviation from intended completion: acceptance could not start because the
required gate failed. The stop follows the authorization; no alternative path
or settings change was attempted.
