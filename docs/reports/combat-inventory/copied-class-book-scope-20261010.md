# Complete copied-class book metadata

The Zobal 8559 / effect413075 family1002 rejection was a catalog scope gap. `owned_spell_records` includes shared breed -2 passives, while the original 813-reference copy flags export covered class roots and grants only. The missing references were 4956, 4957, 4958, 5144, 5145, 5146, 5237 and 5621. Casting definitions already existed.

The original client exporter `sniffer/java/ExportNativeCopiedClassSpellFlags.java` now accepts an optional third argument containing the current published `spells.json`. It unions every owned reference with the existing class/grant scope before reading original `fyF.elO`, `gtQ`, and `eVg.fa/fLF/rpl`. The bounded 256 MB export produced 821 rows, zero missing. All 813 previously published rows and MX constructor bounds were unchanged.

`server/tools/stage_native_copy_book_flags.py` stages an immutable complete revision from the currently active release. It preserves every other document and record, verifies the resulting manifest, rejects changed existing flags/bounds/provenance, and never activates the revision. Use its `--expected-revision` fence and standard catalog credentials; activation belongs to the coordinated full world release.

Private reproducible export input/output are under `.runtime/zobal-copy-metadata-20261010/`. Runtime selection guards remain intact. `CopiedBookCatalogCoverageTests` checks all currently owned class and universal passive references; staging tests reject altered flags, constructor metadata, provenance and duplicate scope.

The staged complete release is `879c0fcabd8e195869bff59f451605017b52666970643af8e1a912cb73ad6a51`, based on active `a3272ec3b722c5923cdfb619041bab41a14c85d9838364440e5f71b9b2254095`. Its canonical replacement document SHA256 is `a0c040686424b660220e7ccc7b34cdf30603e8e7c6153ab0e5711de138d46b1d`. Activation was not performed. Staged validation passed seven tests and the actual 8559 lifecycle (copied 7066 committed, source preserved); the audit observed unrelated concurrent mining source drift.

To regenerate, obtain the current published class/grant scope and `spells.json` through the catalog export workflow, then compile and invoke:

```sh
javac -cp 'client/lib/*' -d /tmp/wakemu-copy-flags sniffer/java/ExportNativeCopiedClassSpellFlags.java
java -Xmx256m -cp '/tmp/wakemu-copy-flags:client/lib/*' ExportNativeCopiedClassSpellFlags class-scope.json copied-flags.json spells.json
```

Preserve the published constructor/source provenance fields when merging the export; the staging validator rejects changes to those fields. Stage with `server/tools/stage_native_copy_book_flags.py copied-flags.json --expected-revision REVISION --dsn DSN --password-file PASSWORD_FILE`. No private capture is required or distributed. Coverage uses the authoritative `BREEDS` keys, including Huppermage 19, rather than an assumed contiguous class range.
