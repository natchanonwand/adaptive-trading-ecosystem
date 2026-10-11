# Phase 5C.1 controlled experiment runner

Research baseline: `phase5c-contract-v0.1.0`. Presentation baseline:
`ui-retro-v0.2.0`. This phase qualifies software using synthetic boundaries only.
It does not authorize a real campaign, additional Gold Scalper executions, OOS,
adaptive search, or Phase 5C.2.

## Architecture and immutable planning

`campaigns` consumes the unchanged Phase 5C.0 contracts and ordinal generator.
`campaign_store` persists one ordered plan per FROZEN definition in a new campaign
ledger. The definition, baseline, parameter space, budget, split, objectives,
constraints, candidate and versioned execution policies participate in identities.
The ledger envelope, plan and frozen selection are independently hash checked on
read. The original contract-only Campaign/Run models remain unchanged; runtime
state uses protocol `CONTROLLED_DEVELOPMENT_VALIDATION_V1`.

GRID uses the registered mixed-radix enumeration. RANDOM_SEEDED uses the existing
seeded counter sampler. Numeric representations are canonicalized before identity
calculation. Duplicate assignments collapse in first-occurrence order, without
replenishing sampling slots or increasing the declared configuration budget.

`campaign_runner.Runner` obtains a PostgreSQL session advisory lock across campaigns.
Each run has a deterministic ID derived from plan, candidate and split identities.
It reserves native budget transactionally before handing work to Phase 5B. A
reservation conservatively consumes budget even if preparation prevents a native
launch. The persisted absolute deadline is never reset by restart/resume.

## Selection, isolation and failure policy

Only DEVELOPMENT observations can enter selection. Execution failures are excluded;
declared constraints are checked before objectives. Missing required metrics are
ineligible. For DECLARED_LEXICOGRAPHIC, all tied winners are selected; for
PARETO_REVIEW, all nondominated eligible candidates are selected in original order.
These policies are bound into the plan and shown through selection decisions.
There is no undeclared profit ranking, champion or production designation.

The development selection and its source observation digest are frozen before any
VALIDATION reservation. Validation only records evidence for that selection; it
cannot regenerate candidates or alter selection. The scheduling code and baseline
boundary accept only DEVELOPMENT/VALIDATION. OOS/unsupported API actions are denied
and audited. The UI has no OOS action or performance preview.

An individual failure records its typed outcome and does not retry. Other candidates
can continue within budget. COMPLETE, PARTIAL, NO_ELIGIBLE_SELECTION,
BUDGET_EXHAUSTED and CANCELLED describe campaign completion. Zero trades is a valid
observation; denominator-dependent metrics remain null. Metrics are never invented.

## Existing execution and recovery

`BaselineBoundary` uses the existing Phase 5B `Service`, artifact authorization,
adapter, process lifecycle, parser, report validation and immutable run evidence.
Derived split/input configurations are new records; the baseline configuration and
prior runs/results/publications are never updated. Configuration/input creation is
validated with the existing Phase 5B input checks. Optimization remains disabled.

On resume, an already reserved run is recovered by ID, never launched again.
Completed evidence is linked back without duplication. An unlaunched/indeterminate
reservation is recorded as INTERRUPTED_NOT_RETRIED. An actually active native run
requires ownership reconciliation and blocks resume rather than risking overlap.
Service restart does not automatically resume any campaign.

Cancellation is persisted, stops new scheduling and signals only the owned Phase
5B service execution. Completed observations and consumed reservations remain.
Loss of the monitoring database connection cancels the owned operation. The existing
Phase 5B process lock also prevents concurrent ordinary baseline/native execution.

The qualified metric adapter currently exposes NET_PROFIT, TRADE_COUNT and
PROFIT_FACTOR for EXPLORATORY_GROSS. Other objective/constraint metrics fail before
launch with `UNSUPPORTED_REGISTERED_METRIC_REQUIRES_QUALIFIED_EXTRACTOR`; COST_MODELED
fails with `COST_MODELED_METRICS_REQUIRE_QUALIFIED_EXTRACTOR`. The frozen contract's
prose does not justify inventing risk normalization, costs or temporal stability
formulas. Additional extractors require explicit qualification.

## Persistence and API

An additive migration lineage (`alembic-campaigns.ini`) creates
`workbench.experiment_campaigns` and its own version table. It requires the existing
baseline migration head and leaves every frozen migration unchanged. Migration
reapplication is tested; destructive downgrade is refused.

After existing migrations, installation uses:

```powershell
.venv/Scripts/python.exe -m alembic -c alembic-campaigns.ini upgrade head
```

Use the normal configured database environment; never put credentials in commands
or tracked files. No production campaign records are created by installation.

The local same-origin API adds:

| Method / path | Behavior |
| --- | --- |
| POST `/workbench-api/campaigns` | Confirmed creation from definition ID + identity; plan only |
| GET `/workbench-api/campaigns?definition_id=...` | Inspect definition's campaign |
| GET `/workbench-api/campaigns/:id` | Plan, candidates, budget, runs, selection and audit |
| POST `/workbench-api/campaigns/:id/start` | Explicit confirmed start/resume |
| POST `/workbench-api/campaigns/:id/cancel` | Confirmed cancellation request |

Creating/freezing a definition or opening the Workbench never starts execution.
Campaign inspection itself is an explicit read action. Start/resume has a separate
confirmation checkbox. The minimal panel uses frozen Retro primitives and shows
outcomes, budget reservations, selection, identities and zero/null metrics.

## Verification

Run `scripts/verify_phase5_c1.ps1` with `TE_TEST_DATABASE_URL` pointing to the local
PostgreSQL maintenance database. Integration tests create isolated disposable test
databases; synthetic native callbacks never execute MT5. The gate retains old
tests, runs the complete regression and quality suite, verifies all historical
hashes and tags, and checks that live campaign/experiment records remain zero.

Phase 5C.2 requires a separate authorization, a frozen software checkpoint and a
reviewed supported objective/constraint contract. This implementation review does
not grant permission to start a real campaign.
