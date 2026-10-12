# UI-2 — Retro Experiment Lab

Presentation baseline: `ui-retro-v0.2.0`. Research baseline:
`phase5c-runner-v0.1.0`. Backend contracts, identities, budgets, split rules,
selection and execution remain unchanged.

The Experiments surface uses the existing navy/cyan design tokens, Retro panels,
status badges, semantic tables and copyable identities. A definition selector and
status precede the dossier. Review areas show the research hypothesis, candidate,
search method, evidence classification, protocol, parameter register, budgets,
objectives and hard constraints. Draft fields remain editable through the existing
API flow; frozen fields collapse into a read-only inspection disclosure.

The protocol sequence is descriptive rather than animated progress: DEVELOPMENT,
SELECTION FROZEN, VALIDATION and SEALED LOCKED OOS. Only registered dates are shown.
There is no OOS performance, preview, run or unlock control.

Budget meters distinguish used, remaining and maximum. Unloaded usage stays null
and displays an em dash; no animated or fictitious progress is shown. The candidate
meter counts retained unique configurations, not discarded duplicate sample slots.
Duplicates do not replenish slots and a frozen plan cannot grow. Execution usage
means conservative reservations, which can include blocked preparations. Unused
capacity is not an instruction to spend it.

The parameter register shows names/native keys, types, baseline values, domains,
provenance/source references and declared conditions. No missing parameter value
is manufactured. Candidate rows join the actual plan identities to persisted
split/run outcomes and metrics. Development decisions are shown verbatim; separate
constraint/objective scores are not invented when absent from the API.

Only NET_PROFIT, TRADE_COUNT and PROFIT_FACTOR are offered as new metric selections.
New objective fields start blank, requiring explicit choice. EXPLORATORY_GROSS is
the only offered classification. Previously saved unsupported declarations remain
visible as disabled options and are never automatically rewritten. Gross evidence
is not relabeled cost-modeled or production-qualified. NET_PROFIT is the native
metric name, not an upgrade of the evidence classification. Zero stays zero; null
stays an em dash.

The current API has no authoritative per-campaign execution-authorization field.
Consequently UI-2 leaves Start/resume disabled and has no start request handler.
Creating a plan is still a distinct, explicit action; it never starts execution.
No plan is created in production during this UI review. Inspect/refresh/cancel
retain their existing API semantics. This presentation gate does not change the
backend or claim to be a backend authorization mechanism.

Accessibility uses visible focus, native disclosure/select/button/meter elements,
named semantic tables and state text alongside color. Dense tables scroll within
their own keyboard-focusable regions. The layout collapses to one column at small
widths; no new animation bypasses the frozen reduced-motion rules.

Browser review must use the actual Workbench for the empty draft plus a disposable
synthetic database for saved DRAFT, FROZEN without a campaign, and campaign fixture
states. Native process and Service.start calls are explicitly disabled in that
review fixture. Production data and historical evidence remain untouched.

Run `scripts/verify_ui2.ps1` for the complete frontend/quality/preservation gate.
UI-2 does not authorize Phase 5C.2, a real campaign, new metrics, tuning, OOS or UI-3.
