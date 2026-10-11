# eYW actual spell container element PC

## Representative

Frozen bounded monster3696 (Corbot C-800), spell4881 at80, fails five attempts with `Missing actual native fyG spell element PC`. Other attempts fail native casting range eligibility independently.

The trap damage-copy implementation already handled ordered PA deltas, but the area producer omitted the spell element operand. Native `eYW.fQG` does not use an outer cast plan or an arbitrary elemental mastery mapping. After the copy-all-property branch, actual PL type11 is cast to fyG; `fyG.gtZ()->fyF.gtQ()->eVg.fa()->fLC()` supplies the source characteristic, and copying occurs only if sourcePV.a(PC) is true. Source extract `.runtime/local/native-limit-eYW.txt`.

## Native null is meaningful

Actual existing spell-element metadata identifies4881 as PHYSICAL0. Installed `eVg.fa(0).fLC()` is null. It must not become generic damagePC20. SUPPORT9 is also null; FIRE1/WATER2/EARTH3/AIR4/STASIS5/LIGHT6 map to actualPC21/22/23/24/90/109.

An installed-Java eGj subclass with actual `frm=ffh` calls the unchanged `eGj.a(element.fLC())` method. PHYSICAL and SUPPORT returnfalse; the six elemental PCs returntrue. The source eGj method delegates to frm.g(PC), and native ffh/eRF guard null presence. Proof `.runtime/monster-blocker-recovery-20261011/faw-pa/ProbeNativeSpellElementPresence.java` and `native-element-presence.json`.

## General producer

`combat_spell_element_pc.py` resolves the actual retained PL packed reference, requires present fyG/type11/spell identity consistency, looks up existing spell metadata, then validates the separate native enum table by element ID/name/source. It returns a typed operand distinguishing proven null from missing metadata. Unknown catalogs, inconsistent identity, invalid PC IDs or missing native null-absence authority reject.

`ExportNativeSpellElementDamagePCs.java` exports the eight enum rows and actual ffh.g(null) result without loading content or connecting services. This separate additive catalog avoids rewriting shared spell metadata. The older full-spell exporter was briefly tried with128MiB and failed during content loading with OOM; it was not retried and its source edit was reverted. The final enum exporter and presence probe each run with64MiB.

The area handler supplies a lazy producer using the actual retained descriptor and packed identity. It is consumed only when eYW has an actual sgQ, lacks copy-all-property, and PLtype11 requires the element branch. Proven null skips only the native final elemental delta, preserving earlier generic damage and ordered deltas. Plain areas do not demand irrelevant metadata. The strict faW308 copy-authority rejection remains before UID allocation.

## Offline verification

Six NEW tests pass: all eight installed enum rows against actual existing spell metadata, actual4881 null handling, actual elemental packed-container handling and ordered delta, malformed identity/missing metadata/null proof, lazy non-damage guard, and complete real area handler308→trap creation→actual PL→copy path. Twelve unchanged trap/snapshot methods also passed before the final wiring method was added. Independent bounded gate requested.

Sealed enum fixture: `server/tests/fixtures/monster_spell_element_damage_pcs_native.json`. Candidate catalog: `.runtime/monster-blocker-recovery-20261011/faw-pa/native-spell-element-damage-pcs.json`. Neither active catalog nor services were changed. The separate catalog must be qualified into the eventual candidate; its absence fails closed. Actual monster3696 replay remains pending; no activation readiness is claimed.

Independent Luna validation passed25/25 with stable selected-source hashes: NEW6, unchanged snapshot5/trap7/life-steal3, and zero-copy4 verifying the faW308 boundary. Receipt `.runtime/monster-blocker-recovery-20261011/offline-area-spell-element-pc-tests.json` and companion log. All scoped offline gates are clean; actual3696 replay and candidate catalog incorporation remain separate requirements.

## Append-only candidate packaging

`server/tools/export_monster_spell_element_damage_pcs.py --output .runtime/monster-blocker-recovery-20261011/faw-pa/native-spell-element-damage-pcs.json` reproduces the bounded64MiB enum export and emits a source-bound receipt. Validation requires the exact native contract/null-absence marker, eight canonical signed-byte element identities with matching row IDs, distinct element names, explicit null versus signed-byte PC IDs, and installed JAR/exporter/document hashes. Source drift invalidates the receipt.

`prepare_monster_spell_activation.py --spell-element-damage-pcs <export>` integrates this document through the existing additional-documents candidate path. It appends an absent document, keeps an identical existing shared document, and rejects replacement when existing shared bytes differ. This hook does not publish anything; existing candidate preparation and activation gates remain authoritative.

Three NEW packaging tests pass locally, covering append/identical/conflict/source drift, malformed native identity/null/PC data, and sealed exact native population. The real exporter completed and self-verified its receipt; CLI help and syntax checks passed without database access. Independent small gate requested.

Independent Luna packaging gate passed3/3 with stable exporter/preparation/test hashes. Receipt `.runtime/monster-blocker-recovery-20261011/offline-spell-element-pc-package-tests.json`. No old suites were repeated and no database or service operation occurred.
