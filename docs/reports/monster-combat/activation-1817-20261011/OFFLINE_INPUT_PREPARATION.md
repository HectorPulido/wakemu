# Frozen 1817-reference input preparation

This is a structural source audit, not activation or runtime qualification. No services or database were accessed. The frozen scope contains 1817 references. The historical dependency-ready candidate selected 721 references, leaving 1096:

| Category | References | Next operation |
|---|---:|---|
| Existing candidate policy already contains the reference | 854 | Requalify current implementation; avoid duplicate native export |
| Native sealed source available, owned book absent from candidate | 203 | Convert/reuse sealed source and append exact missing dependency records |
| Owned and dependency spell books already present | 32 | Validate unchanged dependencies and add explicit policy only after qualification |
| Explicit special encounter exceptions | 7 | Preserve exclusion; do not adapt to ordinary combat |

All 1096 resolve their inventory spell, effect and state IDs in the sealed native source. No row has an inventory missing-definition, missing-casting-table or missing-root-metadata marker. This establishes table availability only. Typed converter completeness, source hash compatibility, per-level domains, dynamic dependencies and actual behavior still require validation.

The seven exceptions are trainer 3174 and racing actors 3976, 3980–3984. Their membership in this frozen scope does not supersede the user's explicit exclusion.

42 references have native minimum level zero (37 among missing books, five among books already present). `select_candidates` currently requires minimum level at least one. Keep exact zero levels and classify them explicitly rather than inventing level one or silently excluding them. High maximum levels also require exact domain checks: source record membership does not certify level 201–245, 630 or 30000 evaluation.

## Reproduction

Run from the repository root:

```sh
python3 .runtime/monster-activation-1817-20261011/audit_remaining_inputs.py
```

The output is `remaining-input-audit.json`, with streaming SHA256 receipts for every source and separate reference files per category. The source catalogs remain unchanged. Four additional integrity checks passed: unique 1096 references, category sum 1096, no missing sealed source IDs, no native inventory gap markers.

## Fast preparation path

1. Pin the existing candidate and native bundle by receipt; use the offline loader being prepared separately. Do not invoke the preparation tool's current unconditional Java export or PG branch.
2. Start with `small-batch-book-present-level1-200-refs.txt`: 17 references whose owned/dependency spell IDs already exist and whose entire native level interval lies in 1–200. They remain unqualified; state/catalog/domain closure must pass before policy admission.
3. Process the remaining 15 already-present books separately for zero or larger domains.
4. Convert sealed native trees for the 203 missing books, preserving original spell ownership, zero roots, parameter curves, bounds and native initial-state triples. Reuse `merge_records`/`merge_npc` only after collision validation; never replace a mismatching shared definition. Import all typed dependency tables, not only spell/effect IDs.
5. Export only a bounded proven missing domain or metadata field if validation identifies one. There is currently no table-existence reason for another whole Java export.

The existing preparation tool requires coverage registry/source hashes and inventory/provenance checks, performs native Java export before connecting read-only to PG, checks shared states/effects, and finally merges candidate ownership. Its existing CLI is therefore not an offline command. The offline pinned loader must replace those input operations explicitly while preserving the same validation obligations.

## Source candidate prepared

`candidateimport235-source-offline` was generated from the pinned `candidate721-offline-native-casting` variant. It imports exact sealed books/effects/casting-root records for **193 positive-level references**, with candidate policy intents and native constructor triples. The remaining **42 native minimum-zero references are explicitly blocked** as `unsupported_native_zero_level_activation`. No conflicting shared definition was overwritten. The original candidate policy remains present; this is not a new runtime release.

The manifest binds the parent manifest, sealed tables, inventory audit, generator, helper and installed client JAR. Shared documents are immutable hardlinks; changed NPC and casting-root documents are separate files. The source import report lists all 235 requested references, their dependency identities and blockers. The helper preserves activation policy itself; the artifact generator uses the existing candidate policy merge only after source import.

**This package is not execution-qualified.** Its manifest explicitly records `qualification=false` and `dependency_catalogs_revalidated=false`. Shared state/resource cost/summon/profile/resistance/cell-group metadata and exact level coverage must still be checked by the offline validator. Candidate policy presence must not be interpreted as an activation count.

New focused helper tests: five passed locally and five independently through Luna. Existing tests were unchanged. The deferred 982 optional runtime hunks were removed precisely before this work; no 982 handler was registered.

## Unified cohort package

`candidate1768-offline-source-qualified` unifies the 854 historical policy references, 721 earlier selected candidates and 193 new positive-level imports. Its selected references and actual NPC policy both equal the exact frozen 1817 scope minus 42 native-zero references and seven encounter exceptions. Every selected min/max interval and owned-spell list matches the frozen descriptor. Dependency union counts are 2732 spell IDs, 2427 state IDs and 39008 effect IDs; these are identities, not passing execution cases.

The package adds an explicit `spells.json` offline rebase from the installed source-qualified snapshot, verifying client JAR and bdata/66 hashes. It retains the parent import's NPC/casting-root hashes and records the original and new shared source seals. Original active shared bytes were unavailable for the rebased catalogs, so this is explicitly **not** a live class-preservation assertion. Qualification remains false. Subsequent shared-catalog rebases are owned by the dependency agent as separate immutable variants; this package must not be overwritten.
