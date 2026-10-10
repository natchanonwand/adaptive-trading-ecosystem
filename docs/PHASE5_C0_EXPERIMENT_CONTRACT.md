# Phase 5C.0 experiment contracts

This phase defines and reviews research protocols. It does not execute experiments,
launch a native tester, select a champion, expose OOS performance, or qualify a strategy.
Phase 5B baseline configurations, runs, results and derived publications remain separate.

## Definition and provenance

`ExperimentDefinition` is an immutable, versioned value containing the existing project,
candidate and baseline configuration identities; hypothesis; parameter space; budget;
split plan; objectives and hard constraints; broker, symbol, timeframe, real-tick model,
data identity, cost assumptions and exploratory evidence classification.
Qualification eligibility is always false. Storage checks the persisted baseline identity
and project binding before registration and again before freezing.

Each parameter declares its native key, type, baseline, bounded domain, identity
transformation, order/category semantics, reason and explicit provenance reference.
Accepted provenance is vendor documentation, user declaration, strategy specification,
or a registered hypothesis. No commercial binary inspection or hidden tester-default
input discovery is implemented. Conditional inputs reference an earlier declared input;
inactive inputs retain their declared baseline. Invalid domains and dependency cycles
are rejected. No actual Gold Scalper parameter space has been registered.

## Budget and reproducibility

Budget pre-registers configuration and native-execution limits, wall time, one worker,
early-rejection policy and GRID or RANDOM_SEEDED method. Random sampling requires an
explicit seed. These are planning contracts, not a scheduler or runtime budget service.

The pure ordinal lookup is exercised with synthetic fixtures only. GRID uses ordered
mixed-radix indexing. RANDOM_SEEDED uses SHA-256 of definition identity, seed, ordinal
and parameter index, modulo the domain size. Sampling is with replacement; duplicates
consume ordinals. Changing any declaration creates a different definition identity.
No API enumerates a campaign or accepts outcomes to influence candidate generation.

Canonical sorted compact JSON produces SHA-256 content identities for definitions,
parameter spaces, splits, budgets, campaign contracts and planned run contracts.
Array order is meaningful; decimal strings retain their declared representation.
Database definition IDs use UUIDv5 of the content identity. Audit timestamps and random
event IDs are outside the immutable content identity. Campaign/run values are contracts
only: no campaign execution or experiment-run database table is introduced.

## Leakage, objectives and eligibility

Three locked, chronological, non-overlapping half-open date intervals are required:
development, validation and locked OOS. Gaps are allowed; overlaps and empty intervals
are rejected. Feature availability checks accept development dates only. Validation
cannot alter a stored definition. OOS execution, unlocking and relocking are unavailable.
Future integrations must apply these contracts before accessing data; this phase is not
a data engine and does not claim to sandbox arbitrary external research code.

Objectives specify metric, direction, definition and an ineligible null policy. A sole
net-profit objective is rejected. PARETO_REVIEW and DECLARED_LEXICOGRAPHIC are declared
evaluation methods, not implemented ranking engines. Constraints specify finite thresholds,
comparators and rationale. Missing observations remain insufficient evidence; no metrics
are synthesized. Zero trades is an observation that can fail a minimum-trade eligibility
constraint without being reclassified as an execution or parser failure.

## Persistence and API

Migration `0004_experiment_definitions` adds `workbench.experiment_definitions` and
`workbench.experiment_protocol_events`. Definitions embed their contracts in JSONB.
Registration is idempotent. Freeze changes only DRAFT to FROZEN, with a timestamped audit
event; repeated freeze does not duplicate the event. Bodies cannot be edited through
the API. A revised protocol must have a new content identity. Destructive downgrade is
intentionally unsupported.

Local same-origin routes:

- `GET /workbench-api/experiments?project_id=<uuid>` lists definitions.
- `GET /workbench-api/experiments/<uuid>` returns content and identities.
- `POST /workbench-api/experiments` validates and registers a complete definition.
- `POST /workbench-api/experiments/<uuid>/freeze` requires `{"confirmed":true}`.
- Confirmed `run`, `search`, `unlock-oos`, `relock-oos` and `update` actions return 409
  and commit an explicit protocol-violation event. They create no execution.

Payloads are bounded, storage failures sanitized, and prior Workbench routes preserved.
The functional Experiments panel exposes parameter provenance/domain/conditions, budget,
splits, objectives, constraints and baseline/data identities using the current Workbench
style. Backend errors are displayed verbatim. READY means a saved, validated draft ready
for explicit freeze review, never execution readiness. Editing a saved draft creates a new
content-addressed definition on save; old records remain unchanged. Dirty forms disable
freeze until saved again. Freeze requires operator confirmation. Frozen fields are read-only;
future revisions start a new definition. LOCKED_OOS has no execution/unlock affordance.
UI-0 remains deferred. No actual candidate parameter values are prefilled or inferred.

## Verification and operational boundary

`scripts/verify_phase5_c0.ps1` runs regression plus Phase 5B evidence readback and
Phase 5C.0 scope/lineage/preservation checks. PostgreSQL integration tests use isolated
test databases. The additive local schema was deployed after the passing full gate and the Workbench
was restarted with separate runtime logs. No real definition was registered. Browser
verification selected the existing baseline without persisting an experiment.
Phase 5C.1 requires a completed, reviewed and frozen contract plus separate authorization.
