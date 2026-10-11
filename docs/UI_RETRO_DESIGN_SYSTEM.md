# Retro Research Terminal — UI-0

## Principles and visual direction

A serious research workstation with restrained late-1980s computer geometry: navy canvas,
rectangular windows, one/two-pixel borders, hard offset shadows, cyan primary accents and
explicit text statuses. Grid texture stays behind panels, never over evidence. No CRT
warping, flashing, heavy glow, gradients over data, gamified P&L or casino motifs.

## Semantic tokens

Tokens live in `dashboard/src/workbench/workbench.css`, scoped to the Workbench document
through `:root:has(.wb-shell)`. The separate monitoring dashboard retains its existing theme.

| Group | Tokens and values |
|---|---|
| Background | `--bg-canvas` #090f1a; `--bg-panel` #101c2c; `--bg-panel-raised` #18283c; `--bg-input` #0a1422 |
| Border | `--border-default` #425975; `--border-strong` #85a4c2; `--border-muted` #283b52 |
| Text | `--text-primary` #edf4fc; `--text-secondary` #bfcee0; `--text-muted` #99acc5; `--text-inverse` #09121a |
| Accent | `--accent-primary` #72e5e2; `--accent-secondary` #c0a8ff; `--accent-tertiary` #f6ce78 |
| States | ready #72e5e2; success #8be2b2; warning #f6ce78; danger #ffa393; info #a7cdff; unknown #b5bdca; running #c0a8ff; frozen #aac5f7 |
| Interaction | `--focus-ring` #fff0a5; `--shadow-hard` 4px 4px 0 #040810; `--shadow-hard-active` 1px 1px 0 #040810 |

State tokens use the `--state-` prefix. Decorative borders need not carry semantic meaning;
text and visible focus carry identification. Colors are not a readiness decision engine.

## Typography

- Display: Fixedsys / Terminal, falling back to Lucida Console / monospace, used for brand.
- Heading: Lucida Console / Consolas / monospace; compact, high-contrast window titles.
- Body: Segoe UI / system sans for forms, help and dense text.
- Label: Consolas / monospace for short terminal labels.
- Mono: Consolas / Courier New for exact IDs and hashes, with safe wrapping.
- Numeric: Segoe UI / system sans with tabular numerals; never pixel typography.

Fonts are local/system fallbacks. No remote font requests or unlicensed bundled fonts.
Raster-font availability varies; the fallback preserves legibility rather than simulating
pixelation of operational text.

## Layout, spacing and borders

Use 4px multiples: 8/12px control gaps, 16/20px panel internals, 24px section gaps.
Desktop project navigation occupies a 176px rail beside flexible content. At <=800px the
rail becomes wrapped navigation; at <=540px forms and metadata collapse to one column.
Minimum-width zero prevents long identities from forcing page overflow. Data tables use
an explicitly named, focusable horizontal scroll region rather than stacked cards.
Controls have square corners and minimum 38/40px height. Panels use hard shadows, not blur.

## Component inventory

`dashboard/src/workbench/retro.tsx` provides:

- RetroPanel / RetroWindow: title, optional icon, status, actions, body and footer.
- SectionHeader: title, eyebrow and actions.
- Button: primary, secondary, danger, ghost; native disabled and keyboard behavior.
- StatusBadge: explicit label and decorative square indicator; text never suppressed.
- Field / Select / Checkbox: native labeled controls, help/error/read-only support.
- Tabs: semantic navigation buttons, `aria-current`, normal keyboard traversal.
- MetricCard / MetricStrip: supplied values only; never fetch or calculate strategy metrics.
- DataTable: caption, column headers, controlled overflow, row hover/focus-within.
- Callout / EmptyState: explanatory and absent-data content.
- IdentityField / MonoValue: exact readable identifiers, no truncation of evidence.

Existing form markup inherits tokens and control styling. UI-0 does not rewrite complex
Baseline/Experiments forms merely to adopt wrappers. ProgressMeter/DeltaIndicator are
intentionally deferred: no experiment progress or comparison data exists to display.

## Status and null semantics

VERIFIED/COMPLETE/PUBLISHED use success; READY uses ready; RUNNING uses running;
BLOCKED/FAILED use danger; UNKNOWN remains unknown; FROZEN/LOCKED use frozen;
DRAFT/DEMO use informational presentation. Original labels remain visible, including
compound blockers. Styling never changes declarations, observations or API response meaning.

`0` and `0.00` are measured values; `null` displays `—` with an unavailable accessible label.
Missing metrics are never zero-filled. Overview cards show only registered artifact byte
sizes and configuration count when supplied. They do not invent performance or campaign data.

## Accessibility and motion

Preserve native controls, labels, headings, region names and column headers. Focus uses a
three-pixel visible outline; hover and pressed states are supplementary. Disabled controls
remain native disabled, and readonly fields remain selectable. Status text accompanies color.
Do not put raster display fonts in tables, timestamps, hashes or help copy. No blinking or
continuous animation is introduced. Reduced motion disables transitions/animation and the
one-pixel button press displacement.

## Do / don't

Do show `UNKNOWN` as explicit unknown metadata. Don't color it as license denial.
Do show actual zero trades separately from unavailable win rate. Don't imply strategy quality.
Do preserve full identities with wrapping. Don't truncate hashes to decorative fragments.
Do use read-only Overview to validate the visual system. Don't create fake runs/progress.
Do require existing explicit research confirmations. Don't turn retro styling into shortcuts.

## Rollout

UI-0 covers the shell, reusable foundation and Overview only. Experiments inherits theme
but retains its functional layout and contract. Suggested UI-1, after separate authorization:
apply the primitives to evidence/run tables and publication readback, with null/zero and
identity regression tests. Then review dense forms separately. Never couple rollout to
Phase 5C.1 execution, optimization, new API semantics or automatic OOS access.
