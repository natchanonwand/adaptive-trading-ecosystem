# Phase 4E — Real External EA Qualification Campaign

Phase 4D is frozen at local checkpoint `4ce8a06`. Campaign tooling wraps its
unchanged observer, feature builder and behavioral research engine. A passing
software gate does not establish real EA qualification.

## Acceptance and provenance

The user selects and installs a properly licensed DEMO EA. File presence, a
trade comment or a magic number alone is not proof of installation rights,
activation or exclusive attribution. Never download, activate, inspect EX5
contents, change inputs, enable Algo Trading or restart MT5 through this tooling.

`RealEaQualificationCampaign` is a frozen Pydantic contract. Store its JSON and
any private settings references only under `.local/phase4_e/` (Git ignored).
It records campaign/account UUIDs, broker/server, terminal build, a single
candidate, license attestation, chart/timeframes, settings SHA-256, local
settings reference, explicit UTC window, observer configuration, feature
version and research code hash. Journal records bind the entire configuration
hash. A settings or identity change requires a new campaign.

The candidate must have a vendor, EXTERNAL_EA source, an exclusive binding
reference and nonzero magic numbers. These conservative acceptance constraints
do not change Phase 4B's KNOWN/PROBABLE/AMBIGUOUS/UNKNOWN semantics. Manual and
unattributed observations remain retained and excluded from candidate metrics.
An EA without sufficiently identifiable attribution can be observed by prior
tooling but cannot pass this first qualification campaign gate.

`attribution_valid_from` must cover the observer's history lookback plus overlap.
The user must actually attest this period; do not invent an earlier date.
This prevents today's binding from silently attributing old deals. Historical
recovered entries are reported separately from entries during observation.
Preexisting episodes retain frozen incompleteness/censoring rules.
If candidate and unknown/manual fills share an episode, Phase 4E rejects
qualification before feature generation. The frozen research loader selects
whole episodes; this guard prevents an opening candidate label from admitting
later unattributed fills. Such evidence remains retained for review.

## Foreground commands

Use the existing virtual environment. Supply `TE_DATABASE_URL` locally; never
paste it into reports or Git. Run from the repository root on Windows. Start
MT5 manually on the selected DEMO account, the existing Phase 4A bridge, the
Phase 4B observer API, and the dashboard. The observer API's `/health` must
report read-only and healthy; `/api/v1/observer` must return a sessions list.
No new daemon, scheduler, execution gateway or background campaign is created.

```powershell
.venv/Scripts/python.exe -m trading_ecosystem.campaigns preflight --config .local/phase4_e/candidate.json
.venv/Scripts/python.exe -m trading_ecosystem.campaigns run --config .local/phase4_e/candidate.json --output .local/phase4_e/campaigns/<campaign-id>
.venv/Scripts/python.exe -m trading_ecosystem.campaigns status --campaign .local/phase4_e/campaigns/<campaign-id>
.venv/Scripts/python.exe -m trading_ecosystem.campaigns finalize --campaign .local/phase4_e/campaigns/<campaign-id>
.venv/Scripts/python.exe -m trading_ecosystem.campaigns validate --campaign .local/phase4_e/campaigns/<campaign-id>
```

Preflight uses the same supplied configuration as run. A future window fails
until its start; an elapsed window always fails. Configure at most one day per
foreground run and optionally an episode target. There is no automatic extension
until a sample threshold is reached. Run can request one controlled observer
reconstruction with `--restart-after-seconds N`; it never restarts MT5 or the EA.

The operator must keep the exclusive binding/settings stable. MT5's read API
cannot independently prove a proprietary EA's license, chart attachment or
unchanged inputs. The terminal-process presence check precedes SDK attachment;
keep MT5 running through attachment. Native SDK reads can block until SDK timeout.

## Continuity and stop conditions

Start requires fresh bridge health for the same DEMO account, PostgreSQL,
observer API/dashboard health and the static read-only audit. Account/build
guards run before and after each poll. Full service checks run every five
seconds. Account switch/non-DEMO invalidates; disconnect/DB/health failure pauses;
excessive observed polling gaps degrade. Failed campaigns cannot qualify.

Normal stop forces history reconciliation and a position snapshot before STOP.
Open episodes stay open/censored. Keyboard interruption and incomplete journals
require review; there is deliberately no automatic resume or overwrite. A
partially exported campaign is retained, not reused silently. A hash-chain is
tamper evidence, not a digital signature or independent proof of a native source.

Polling latency measures guards, periodic health and observer step; journal
flush and episode-target query time are reflected in subsequent inter-poll gaps.
The report includes processing-budget misses, CPU time, Python allocation peak
(not total RSS), start/end database size and ingestion events/hour including
history. Connectivity is sampled; sub-poll outages are not observable. A fault
ends observation, so reconnect duration after that stop is unknown, not zero.
Research and feature calculations run only after observation stops.

## Offline freeze and independent rebuild

Finalization requires a native-origin, successful start and reconciled stop with
no failed polls or gap records. It independently exports/replays raw evidence
twice, builds Phase 4C features twice, validates them, then builds Phase 4D
research twice. Canonical identities must match. The immutable root manifest
hashes every retained file; validate repeats the frozen validators and derives
the summary again. Creation uses exclusive writes. No real evidence is exported
from software fixtures during the repository integration tests.

The summary reports attribution counts, closed/open episodes, entry days,
directions, symbols, sessions, history entries, recovered events, and all six
timeframes' available/sufficient closed-bar history fractions with denominators.
Commission, fee and swap retain actual signed broker values and unknown counts.
Exit evidence reports native reason codes; price proximity never establishes a
stop-loss/take-profit exit. Basket membership remains unidentified.

Phase 4D outputs already supply fingerprint, temporal/SL/TP/volume/spacing
measurements, outcome separation, hypotheses, support, contradictions and
limitations. Its 30/100/300 and session policies are unchanged. Qualification
means pipeline/sample sufficiency only, not source-code recovery, strategy truth
or investment suitability. No-entry exposure sampling is deferred:
`P(context | observed entry)` cannot be inverted to `P(entry | context)`.

## Quality gate and evidence preservation

```powershell
.\scripts\verify_phase4_e.ps1
```

Requires the existing isolated PostgreSQL test setup, `TE_TEST_DATABASE_URL`,
locked Python dependencies, Node/npm and uv. The gate preserves every tracked
Phase 4D file and 1,044 prior evidence files, runs Phase 4E/4D targeted tests,
the full Phase 2B–4C verifier composition (including PostgreSQL/frontend), and
the unchanged Phase 4D evidence verifier. It deliberately does not call the
Phase 4D readiness collector, which would overwrite frozen readiness metadata.
No checks or old tests are relaxed. `-CodeOnly` excludes historical pipeline
rebuild verification and must not be reported as the full gate.

No new dashboard section or background market sampler is needed for the blocked
first campaign. The existing dashboard and read-only CLI status are sufficient.
Stop after Phase 4E; no GPT calls, cloning, optimization or automated execution.
