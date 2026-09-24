# Phase 4D — Behavioral Research & Analysis Engine

Phase 4C was frozen locally at `90e9091`. This phase uses the independent
`behavioral_research` package, preserving the frozen Phase 3.1 `research`
mathematical kernel and its strict scope test. There
are no dependency, observer, feature-definition, risk, accounting or calibration
changes. Research operates downstream of validated Phase 4C exports.

## Architecture and validation

Observation → Features → Statistical evidence → Hypotheses remains explicit.
`behavioral_research.loader` invokes the unchanged Phase 4C validator: source manifests,
Parquet schemas, source-session identities, code/catalog/config versions, row
counts, canonical hashes, primary keys, X/Y separation, raw replay and dataset
type must pass. It then verifies the exact bytes it reads and enforces one-to-one
episode/outcome joins and entry-parent membership. Unknown types fail closed.
Source exports remain required for strong validation, but no database or terminal
is needed. No live MT5 query is made.

Optional exact candidate, source-session and symbol filters are part of the
hashed research configuration. They select entire episodes with their outcomes
and fill rows; no episode disappears merely because one field is missing.
An empty selection produces explicit zero counts and null measurements.

The analytical unit is an observed episode entry unless explicitly labeled
entry-fill, within-episode ratio or session-cluster. Episode X, entry X and Y
remain separate input tables. Retrospective outcome strata and holding-duration
summaries do not become entry-time features. Unknown attribution is retained in
descriptive counts and cannot support an EA-specific hypothesis.

## Measurements and denominators

Every statistic carries `n`, `known_count` and `missing_count`; rate outputs also
carry successes. Each conditional group has its own denominator. Missing condition
values are counted at the parent table and missing outcomes in the child rate.
All-missing distributions return null, never zero. Counts of known false values
remain observed zeros. Numerical outputs use Decimal34 / half-even; exact numbers
are serialized as decimal strings. JSON disallows NaN/Infinity.

Implemented measurements cover:

- Episode/fill counts, BUY/SELL and symbol distributions, and candidate quality.
- UTC hour, weekday and configured Phase 4C session distributions, with direction,
  entry-volume and holding-duration summaries per group.
- SL/TP usage, absolute and ATR distances, observed reward/risk, change/removal
  rates and counts, and inherited first-observed modification delays.
- Entry/fill volumes, prior volume, volume ratios and ratio conditional on prior
  volume bins, sequence length, scale-in rate, partial closes and within-episode
  volume progression. A reset means a later size returns to or below the first
  observed episode size after an increase; it is not a hidden strategy reset rule.
- Prior known-candidate/same-symbol entry time and price distances, same-direction
  subset, absolute distance divided by positive current-entry M15 ATR, and
  within-episode spacing coefficient of variation. At least two spacings and
  positive mean spacing are required for that coefficient.
- Contemporaneous recorded spread distributions; unavailable spread stays null.
- Price relative to EMA20/50/200, EMA separation, return sign, direction agreement,
  RSI bands, ATR quantiles and range-position quantiles. Both conditional BUY
  proportions and observed-entry context frequencies are stored.
- Outcome summaries, including partial-close/entry counts and net broker P/L,
  and explicitly retrospective WIN/LOSS/FLAT entry-volume/direction strata.
- Prior-adverse-outcome volume/scale-in tables only when an unambiguous previous
  episode in the same candidate/symbol/source session has an outcome available
  by the new entry observation. Volume increase compares those two episode entry
  volumes, not an unrelated fill. Tied predecessor times cannot establish order.
  Phase 4C source-end availability often leaves these pairs unavailable.

**P(entry | context) is not identifiable from an entries-only dataset.** The
engine reports this as unavailable with a reason. It never substitutes
P(context | observed entry), nor invents non-entry observations. Likewise basket
identity is unavailable in Phase 4C; basket-close behavior is explicitly deferred.

Raw-price distances, lots, holding times and outcomes have different units and
coverage. Pooled-symbol summaries are inventory measurements; select a symbol
before interpreting them. No exchange-rate conversion or economic risk estimate
is invented.

## Statistical definitions and uncertainty

Numeric descriptions use Type-7 interpolated quantiles and population standard
deviation. Spearman uses average tied ranks; Pearson infrastructure is available
for meaningful numeric pairs. Fewer than three complete pairs or zero variance
returns null with a reason. Categorical association uses uncorrected descriptive
Cramér's V from the contingency table, never integer-encoded category Pearson
correlations. Empty/constant categories return null. Small-sample upward bias in
uncorrected Cramér's V remains a limitation; it is not a significance test.

Rates include two-sided 95% Wilson score intervals with fixed normal critical
value 1.959963984540054. These are labeled exploratory IID-episode intervals:
correlated entries can make them overconfident. No independence claim is made.
Median intervals resample whole source sessions with replacement, using the
configured seed and 200 bootstrap replicates by default. They require at least
two sessions with known values and use Type-7 2.5/97.5 percentiles. Session
independence is also an assumption; bootstrap intervals are not qualification.

Effect sizes include differences in proportions and uncorrected odds ratios,
with explicit left/right sample counts. Zero odds denominators return null and
`ZERO_DENOMINATOR_NO_PSEUDOCOUNT`, not infinity or a silent continuity correction.
Comparisons report differences in selected descriptive rates and medians, never
rank or declare a winner. Candidate, version/dataset, session and symbol comparisons
use separately configured, fully validated runs. Feature-set mismatch is rejected.

No null-hypothesis significance tests, raw p-values or significance findings are
introduced in this phase. Consequently no FDR-adjusted p-values are fabricated.
If significance testing is added later, its registered test family and correction
(such as BH) must be implemented before emitting findings. This phase's Wilson
intervals and comparisons are descriptive, not multiple-test discoveries.

## Fixed bins and sample policy

Configuration stores RSI cutpoints 30/70 and quantile probabilities .25/.5/.75.
Realized quantile edges, fit population and boundary convention are recorded in
the result. Bins are left-closed/right-open, with unbounded outside bins; ties
produce deduplicated edges. Empty bins have no invented sample. These are
whole-selected-sample descriptions, not train/test transformations. No thresholds
are searched for profitability or changed based on results.

Default sample tiers are INSUFFICIENT below 30 known observations, PRELIMINARY
at 30, USABLE at 100 and STRONGER_EVIDENCE at 300. These are transparent,
configurable operational count labels only. There is no scientific claim that
30, 100 or 300 makes an EA understood. The spec supplied no calibrated thresholds;
these round-count defaults must not be presented as a power calculation or a
confidence probability. Each individual metric still exposes its own smaller
known count even when the aggregate episode count is large.

## Hypothesis contract and guards

`BehaviorHypothesis` supports trend alignment, mean-reversion-like entry,
breakout-like entry, volatility/session filtering, fixed/ATR-scaled exits,
scale-in, grid-like spacing, volume progression and basket close as future
families. This phase instantiates only three prespecified price/EMA direction
alignment hypotheses, and only for REAL_DEMO_OBSERVATION.

SYNTHETIC_QUALIFICATION always yields SOFTWARE_VALIDATION_ONLY and an empty
hypothesis list, even for a perfect large fixture. JSON, Markdown, packet and UI
preserve that guard. Unit tests simulate real-type inputs solely to test the
guard machinery; those fixtures are never exported as real qualification.

For real-type inputs, support requires exactly one known candidate, no unknown
entry-time attribution in the selected sample, at least 100 complete direction
pairs, at least 80% pair coverage and three source sessions with at least 30
complete pairs each. The pooled and every eligible session's Wilson lower bound
must exceed the prespecified 70% agreement threshold. If all corresponding
upper bounds are below 70%, status is CONTRADICTED_BY_CURRENT_SAMPLE; otherwise
WEAK_EVIDENCE. Failure of the sample/identity gates gives INSUFFICIENT_DATA.
These configurable defaults are deliberately restrictive operational evidence
rules, not calibrated strategy truth thresholds. Dependence and market-context
imbalance remain; support means only that the current sample meets that rule.
The confidence field literally says SAMPLE_SUFFICIENCY_ONLY. No TRUE/FALSE rule
verdict, martingale/grid label or proof of indicator usage is produced.

## Identities, artifacts and determinism

`BehaviorFingerprint` carries schema, source-derived definition version/hash,
config hash, Phase 4C feature-set ID, input manifest SHA-256 and measurements.
Changes to research package source alter the definition identity. Research run ID
derives from input manifest hash, configuration and research source hash. Seed is
stored explicitly. The baseline checkpoint identifies frozen Phase 4C; research
source hash identifies the uncommitted Phase 4D implementation.

Exports refuse existing directories. Each writes `research.json`,
`behavior_fingerprint.json`, `behavior_research_packet.json`, `report.md` and a
manifest containing exact file hashes. The packet contains summarized evidence,
provenance, sample counts, hypotheses and limitations, never raw observations.
No external API is called. Runtime `created_at` belongs only to the manifest and
is excluded from research content identity. Repeated artifact bytes and content
hashes must match; manifest timestamps can differ. Validation independently
rebuilds from Phase 4C and compares every artifact, provenance and hash.

## Offline commands

```powershell
.venv\Scripts\python.exe -m trading_ecosystem.behavioral_research validate .local/phase4_c/features-final-v2/normal
.venv\Scripts\python.exe -m trading_ecosystem.behavioral_research fingerprint .local/phase4_c/features-final-v2/normal
.venv\Scripts\python.exe -m trading_ecosystem.behavioral_research analyze .local/phase4_c/features-final-v2/normal --output .local/phase4_d/new-run
.venv\Scripts\python.exe -m trading_ecosystem.behavioral_research validate .local/phase4_d/new-run --research-export
.venv\Scripts\python.exe -m trading_ecosystem.behavioral_research compare .local/phase4_c/features-final-v2/normal --right .local/phase4_c/features-final-v2/stress
.venv\Scripts\python.exe -m trading_ecosystem.behavioral_research report .local/phase4_c/features-final-v2/normal
.venv\Scripts\python.exe -m trading_ecosystem.behavioral_research serve .local/phase4_d/new-run
```

`--config` and `--right-config` accept explicit ResearchConfig JSON. The reader
binds loopback port 8765, exposes GET `/api/v1/behavior-research` only, rejects
nonlocal Host/Origin, and rejects writes. It validates once at startup and serves
an immutable in-memory summary. Stop another offline reader before using its port.
The existing dashboard proxy presents Research Lab on the Research tab; there
are no GPT, clone, generate or execution controls. It shows an unavailable state
if the reader is absent, never a fabricated research fallback. General telemetry
controls are hidden only on the two offline Research/Feature pages.

## Boundaries and limitations

Real external EA data remains NOT PROVIDED. All qualification exports use the
preserved normal/stress Phase 4C synthetic datasets. Numerical/adversarial fixtures
verify algorithms, not strategy performance. Features and research never enter
the observer polling path. Shared dependencies are unchanged, so the optional
polling benchmark rerun is not triggered; Phase 4C timing evidence is preserved.

ADX, clustering, unrestricted rule discovery, significance testing, latent basket
inference and non-entry opportunity modeling are explicitly deferred. Existing
Phase 4C missingness, first-observed semantics, finite context and source access
requirements persist. No frozen verifier is weakened.

`scripts/verify_phase4_d.ps1` composes the unchanged Phase 2B–4C gate, then verifies
984 preserved files: 874 historical, 53 Phase 4B and 57 Phase 4C. It independently
rebuilds Phase 4D outputs. `collect_phase4_d_readiness.py` gathers source-linked
reports, XML test counts, package metadata, startup/architecture references and
available screenshots into ignored local metadata. It does not create a public
README or duplicate unsupported phase claims.

Stop for review after Phase 4D. No Phase 4D commit, tag, push, GPT interpretation,
real behavior classification, cloning, strategy synthesis, optimization or execution.
