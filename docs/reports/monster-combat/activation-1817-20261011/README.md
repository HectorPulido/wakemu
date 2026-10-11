# Fixed 1,817-monster offline activation

The user requests automatic local activation qualification for the exact 1,817 definitions previously reported as having all effect families covered. This is a monster count, not a count of distinct effect families. The scope is frozen from `family-coverage-after991.json`; later handler additions do not expand this cohort.

No service operations, deployment, active-catalog mutation, or publication are authorized in this phase. A local package will enable only monsters that pass the actual activation gates. Failed definitions remain blocked with their exact reason; bounded screening success alone is not full qualification.

## Initial inventory

- Fixed scope: 1,817 definitions.
- Existing source candidate: 721 definitions, all inside this scope.
- Require candidate assembly or dependency screening: 1,096 definitions.
- Seven encounter exceptions remain blocked under the user's existing minigame/mission exclusion. This is a subset of the fixed scope, not an additional category to add to the figures above.
- No new local qualification is claimed at initialization. Existing historical receipts establish priority only unless their full dependency/source context remains valid.

The first small validation batch uses 4521, 5304, 5329, and 5342, each with a single native level and owned spell. Run focused validation first, continue independently across failed references, and defer heavy full-cohort checks until the final gate. Preserve all original test assertions.

## Evidence

Private artifacts live under `.runtime/monster-activation-1817-20261011/`: `scope.json`, `ledger.json`, `validation-priority.json`, and `current-handler-coverage.json`. The ledger distinguishes pending, blocked, and locally qualified definitions. Local qualification does not claim live activation.

The local PostgreSQL read-only probe was denied by the execution sandbox. Offline validation therefore requires an explicitly identified pinned snapshot: every consumed document must match its declared SHA, missing documents must fail closed, and receipts must distinguish declared snapshot metadata from verified raw contents. Do not disguise the snapshot as a live database revision. Deployment-time rebase and validation remain separate work requiring the user's later notice.

## Complete preparation screening

The 1,096 definitions outside the existing 721-reference candidate split into **854 existing-policy definitions requiring requalification**, **203 needing owned-book import**, **32 with books present but requiring policy/dependency validation**, and **7 encounter exceptions**. All sealed native spell/state/effect membership checks passed; this is input availability, not execution proof.

Within the 235 import/policy definitions, **42** have native minimum level zero. The current activation constructor does not support that domain; they are explicitly blocked rather than silently activated from level one. Together with the seven encounter exceptions, the ledger currently has **49 blocked** and **1,768 pending local validation**, with zero newly qualified yet. The common pinned casting-document gap is being addressed through an explicitly identified offline candidate rebase; the old snapshot hashes are never silently overwritten.

## Source import completed

The positive-level remainder now has an offline source candidate for all **193** eligible definitions from the 235 import/policy group. The 42 zero-level definitions remain blocked. The candidate binds sealed native inputs, generator/helper code, inventory, and installed client JAR hashes. Five new import-helper tests pass independently. This prepares policy intents only; dependency validation and actual combat qualification remain pending.

The ledger links those 193 definitions to `candidateimport235-source-offline` without changing their pending status or enabling them. A unified candidate must include all 1,768 eligible scope references so that existing-policy definitions also receive current qualification.

The first actual four-reference batch exposed common missing SHA-qualified baseline assets before monster execution. These are environment failures, not monster failures. Native casting and spell metadata have explicit source-qualified offline replacements; further shared asset discrepancies are audited together to avoid repeated per-monster startup failures. No original test assertions have been relaxed.
