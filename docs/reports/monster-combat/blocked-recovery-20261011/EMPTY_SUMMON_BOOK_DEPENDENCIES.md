# Genuine empty native summon dependency books

Six blocked parents reference five native profiles with genuinely empty ability lists. All five have both sealed `native_abilities=[]` and raw installed `aMb.csd=[]`; none is missing its source field.

| Ordinary parent | Summoned dependency | Source book | Remaining independent issue |
| --- | --- | --- | --- |
| 3924 Aspidupido | 3800 Baliza de destrucción | Explicit empty | Native execution still required |
| 5471 Calabaciflor | 5543 Kaviar la Berenjena | Explicit empty | Native execution still required |
| 5595 Toross Mordal | 5600 | Explicit empty | Native execution still required |
| 5626 Fulgurosaurio | 5660 | Explicit empty | Descriptor level domain remains unproven |
| 5661 Cristal eléctrico | 5660 | Explicit empty | Descriptor level domain remains unproven |
| 2096 Bruja | 2107 | Explicit empty | Native execution still required |

Installed bje.aQc invokes bPD.a(blj.dvR(), descriptorLevel, actualActor) at offsets64–77. bPD.a iterates the list and returns at100 when empty. It does not reject an empty book or synthesize an ability. Existing fresh_action_book already returns a source-qualified actions[] checkpoint for an explicit abilities[] profile; there was no runtime construction bug.

The blocker was parent dependency preparation: attach_summon_dependencies rejected every empty spell_ids list. It now accepts an empty dependency only with the new exporter receipt, which binds its exact profile reference, both present empty native lists, canonical operand hash and full raw native profile hash. Missing, wrong-type, duplicate, inconsistent or bare empty books remain rejected. Original bare-empty regression stays unchanged and passes.

`monster_summon_book_source.py` creates/validates the explicit source receipt. `summon_dependency_scopes` attaches it from the sealed native profile. Preparation preserves the receipt in the ordinary parent's registered_summon_profiles scope. No empty-book profile becomes an enabled wild monster, and no uncertain descriptor level gains an exemption. AI's registered_dependency_enabled already compares actual actions against the scope and never grants a nonexistent action; no AI/runtime bypass was needed.

Validation: four new tests plus four existing dependency-scope tests pass8/8 offline. Exporter owner separately reports16 export regressions passing. Full native parent/summon execution remains pending. Evidence: `.runtime/monster-blocker-recovery-20261011/empty-summon-book-evidence.json` and `empty-summon-book-native/{bje,bPD}.txt`. No catalog publication, services, PostgreSQL or heavyweight tests.

Actual installed native probe `ProbeNativeEmptySummonBook.java` initializes bPD with an explicit empty ability list at descriptor levels0,1,38,128,230,32767 and checks its real action iterator stays empty:6/6PASS. This is the native book constructor branch, not complete summon combat qualification. Its receipt binds the client JAR, probe source, native bytecode and output hashes.
