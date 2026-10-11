# UI-1 research surfaces

UI-1 extends the frozen UI-0 navy/cyan design system with dense run and evidence tables,
compact metric strips, full timezone-bearing timestamps, and accessible identity copying.
It introduces no API, execution, database or experiment contract changes.

The run register uses the existing list endpoint. Inspecting a row performs the existing
read-only detail request, then displays publication availability and execution strategy
when the publication supplies them. The list endpoint does not expose those fields:
uninspected rows explicitly say to inspect for publication; absent strategy is not inferred.
The saved-run selector remains available and execution confirmation/cancellation is preserved.

Run detail separates identity, execution, configuration, immutable outcome, later
reconciliation, derived publication, and evidence. Publication metrics retain the API's
exact precision. Zero is measured zero; null is an em dash with an undefined/not-applicable
label. Currency and percentage units are only attached to known metric fields; ratios are
not silently rescaled. No performance interpretation is added.

Evidence provenance is an ordered compact table from authorization and artifact through
configuration, execution plan, run, report, reconciliation and publication. Missing optional
identities remain unavailable. In particular, the original native report identity is manifest
provenance only: original encoding bytes were not retained. The verified stored UTF-8 report
is distinct. This caveat must not be collapsed into an unconditional original-byte claim.

`ResearchSurfaces.tsx` composes UI-0 primitives and adds reusable CopyValue, Timestamp,
Facts and Metrics components. Copy controls use the native clipboard API, announce success
or failure, and preserve selectable full values. Semantic table regions are keyboard-focusable,
have sticky headers, and retain contained horizontal scrolling on narrow screens.
Reduced motion and focus/contrast tokens are inherited unchanged from UI-0.

Run `scripts/verify_ui1.ps1` from the repository root. It verifies the immediate UI-0
checkpoint, all tag refs, strict UI-only changed-file scope, frozen/historical file hashes,
Phase 5B tables/publication, absence of real experiments, three finalized run manifests,
Python quality/security checks and the full frontend suite/build. Runtime screenshots and
gate logs stay under ignored `.local/ui1/`. UI-1 does not authorize a Git freeze.
