# Phase 3.3B retained evidence audit

Run `phase3_3b-e0a03fae2bf50aadd651586b` is completed using its existing historical results. The completion audit is read-only and does not call the simulation runner.

The writer in `backtests/evidence.py` intentionally writes and verifies an exclusive `.partial` intermediate, then writes and independently verifies the final `.json`, leaving the intermediate in place. This is durable staged evidence, not an interrupted rename. The report already describes retained partial files. All 12 pairs were verified to have identical byte lengths, SHA-256 hashes and parsed content. No companion was deleted and no final JSON was changed.

The default final verification script now also checks the exact final result set and rejects orphaned, conflicting or semantically different partials. Identical retained pairs are unambiguous. Synthetic regression tests cover each rejected state.

The separate completion audit verifies the original source-derived run identity, frozen datasets, all result provenance fields, registry identities, cost assumptions, independently derived split boundaries and the exact report generated from verified JSON. Keeping the audit outside the original backtests package preserves the producing source identity. The `runner.py` AST contains exactly one tick_assumption dictionary key; no duplicate-key change was needed.
