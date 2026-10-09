# Controlled class summon casting: shared authority gaps

This read-only review concerns abilities of class-created summons, not general monster casting or AI. The previously classified class closure introduces 38 additional spell trees and 297 additional effect definitions, reachable through 39 class-referenced entity profiles and 86 summon-ability edges. They exist in the private bulk staging export. Those counts are structural inventory evidence, not proof that the resulting casts execute correctly.

## Current shared blocker

`combat_cast.prepare_spell_cast` requires the active actor to equal the connected player character ID, then validates its spell against that player's deck. `combat_summon_creation` correctly gives a non-self-controlled summon its caster's owner/control relationship, but initializes its native spellbook authority as an empty dictionary. Consequently, the owned active summon cannot cast a native ability through the ordinary request path. Removing the player-ID comparison alone would also apply the wrong deck and spell UID rule.

## Native identity and book evidence

The actual request caller `dbk.ad` puts `big.Sn()` and `bPO.LV()` into `cpm`, opcode 13260. The second signed 64-bit field is an owned action instance UID, not universally a spell reference, actor-packed UID or spell-level container QF.

For the concrete NPC/summon book, `bje.dok()` delegates to `bPD.elj()`, and `bje.js(long)` delegates to exact UID lookup `bPD.js(long)`. `bPD.a(ArrayList<ayB<bPK>>, short, eGj)` constructs each native `bPO` with UID `(long)definition.d()`. `bPO` stores this constructor UID in `bfx`, and inherited `fyG.LV()` returns that field unchanged. Thus these profile abilities use raw spell-reference UIDs scoped to the actual actor's book. This differs from ordinary player's actor-packed spell UID and from `fyG.QF()`, which constructs the separate spell-level container identity.

The selected ability level is an explicit profile override when `ayB.bTV()!=-1`; otherwise the supplied short level is used, then `bPO` clamps it to `bPK.Fq()`. `bje.aQc()` supplies actor level, whereas `bje.dsj()` rebuilds the book using actor level divided by two. The actual creation/deserialization/refresh ordering must be closed before selecting one producer for runtime authority; an unconditional actor-level rule is not established by this review.

`bje.dos()` may filter ability presentation using the descriptor's controller actor, but `dok/js` still use the summon-owned book. Controller presentation must not become permission to cast the controller's entire player deck. The installed class named `ctM` is an unrelated opcode-22728 string message; that name supplies no spellbook evidence in this client version. `eHd` is the actor snapshot/deserialization object, not sufficient evidence for the request UID.

Offline disassemblies are saved under `.runtime/combat-review-20261007/controlled-summon-proof/`. Request-caller evidence is `.runtime/local/combat-cast-caller.txt`. No running client, AI, service or database was used.

## Minimal general implementation proposal

1. Import only the 38 classified class-summon dependency trees and 297 missing definitions, preserving all branches and exact effect identities. Join current authoritative casting metadata rather than infer missing fields from the old structural exporter. Follow their state/area/grant references and report any new unresolved closure; do not import the general monster catalog.
2. Produce a complete summon-owned action book from its actual native profile ability records, selected native levels and instance UIDs at the proven lifecycle boundary. Keep empty known books distinct from unavailable authority. Preserve explicit ability-level overrides and definition maxima.
3. Resolve a cast against the owned active actor's authoritative book: player actors retain their deck rules; controlled class summons use their own registered book. Validate exact action UID and book membership before resolving roots. Preserve session owner, active-turn identity, living actor, control and controller-chain checks. Temporary grants remain a separately attested UID source.
4. Resolve resources, effective range, targeting, conditions, retained ownership and delivery through the existing shared pipeline. Do not add creature-specific exceptions, AI choices or general NPC request access.
5. Validate forged UID/foreign ability/controller deck rejection, inactive and foreign-owner summons, native level selection and cap zero, distinct summon instances with identical raw ability UIDs, summon removal, and whole-system lifecycle/delivery. Structural import or successful preparation must not be reported as client verification.

The 38/297 list comes from the prior hashed class-only closure report; a fresh pre/post source manifest was not collected for this read-only follow-up. Current production sources are shared and may continue to change. No implementation or catalog edit is included here.

## Fresh creation level producer closed

The native fresh family-307 path establishes descriptor level, rather than the unrelated refresh half-level:

- `eZl.c(Qe,boolean)`, offsets 40–75: invokes `eGj.b(...eHD...)` with the actual descriptor.
- Concrete `big.b(...)`: resolves the native profile, chooses an existing actor or fresh `bje`, and invokes its private creation routine.
- `big.a(big,long,aBn,eHD,boolean,blj,SQ,eHN)`, offsets 19–30: initializes the actor, invokes `actor.aQc()` at 23, then invokes `eHD.a(actor,caster)` at 30.
- Its initialization helper `big.a(big,long,aBn,eHD,blj)`, offsets 16–22: sets actor level using `actor.bz(descriptor.cmZ())` before the `aQc` call.
- `bje.aQc()`, offsets 65–77: supplies `blj.dvR()` and the actor's current short level to `bPD.a`.

Therefore, fresh class-summon ability construction uses the actual descriptor level, except explicit profile overrides, and clamps to each definition's maximum. No `dsj()` invocation occurs along this creation path. Later refreshes that call `dsj()` are a separate transition and require an explicit producer rather than silently retaining the fresh rule forever.

The native `big.ab` final creation step also rebuilds shortcut presentation; its conditional `ffe.sfy` branch uses the controller's deck for that presentation. It does not establish replacement of `bPD.dok/js` ownership with the player's book. A general producer must keep these separate.

Additional bytecode evidence is saved as `controlled-summon-proof/wakemu-summon-eHD.txt`, `wakemu-summon-eZl.txt`, and `big-creation.txt`. This closes source-level fresh-book level selection; an actual offline native book probe and integrated request/lifecycle tests remain required before claiming executable support.

## Native scoped profile export and book probe

Private `controlled-summon-proof/abilities.json` now contains all 39 structurally class-referenced native profiles, with 86 ordered ability records and 43 unique ability references. Each record preserves reference, explicit override level, native maximum level and native casting UID. All 86 overrides are `-1` in this installed dataset; the producer contract still retains explicit override support rather than assuming that property for future exports. Thirty-eight of the 43 ability trees were absent from the local union at the earlier structural review.

`ExportNativeClassSummonAbilities.java` converts actual native profiles and exercises actual `bPD.a`, `bPO`, `fyG.LV`, `bPD.js`, and `bPD.elj` for each ability at fresh levels 0, 1, 20 and 200. All 344 native constructor checks passed: raw-reference UID, exact clamped level and identity-preserving book lookup. These checks do not execute ability effects or attest connected casting/client delivery.

Private `manifest.json` records source hashes for installed client library/data jars, the exporter, profile seed list, native output and closure evidence. Profiles were scoped by classified traversal from the 813 class/extras roots and native innates; no general NPC/monster catalog was imported. No production Python or protocol data was changed by this export.

## Shared fresh-book implementation checkpoint

The source now implements the fresh class-summon book rather than granting access to a player's deck. `combat_summon_spellbook` reads the scoped 39-profile/86-record native export from `native-class-summon-abilities.json`, constructs exact raw-reference casting UIDs, preserves explicit override levels including zero, and clamps to native definition maxima. Fresh creation stores a plain checkpoint-safe action book. Registered actor authority reconstructs `NativeSpellBook` from that book after checking its creation provenance. Missing profiles, altered books and unavailable later refresh producers remain explicit errors.

The common action resolver validates the owned active actor before resolving either the player's deck, a separately registered temporary grant, or the controlled summon actor's own book. The summon route follows actual registered controller links to the connected character, rejects cycles, missing controllers, foreign owners and stale provenance, and checks the exact UID inside that actor's scoped book. Two summons may own the same raw-reference UID; their actor identities remain separate. The server preparation path uses the resolved actual actor for WP and critical chance, and the actual book-selected level for critical availability. Transaction cast packets identify the actual caster. A companion delivery change resolves the connected player's session snapshot and serializes summoned actor statistics separately; see `controlled-summon-cast-delivery-review-20261007.md`.

Only class-referenced dependency data was imported: 38 additional trees and 297 additional effect definitions. The dependency importer verifies all 43 book references and their full native level domains. An explicit native zero-level export covers 43 ability references and 319 effect definitions. Its merge adds 38 zero root/casting records and 297 closure references to the existing snapshot, with every overlapping record identical. The resulting zero snapshot contains 851 spell records and 13,599 effect references. Existing records were preserved; private before/after hashes and backups are under `controlled-summon-proof/level-zero/`.

The old critical-availability export sampled levels 1 through 200, which did not attest zero or native summon maxima of 245. A scoped original-client probe now checks every level from zero through each native maximum: 10,339 `bPO.hasCriticalEffect` constructor checks across 43 references passed. The availability merge preserves the previous 1–200 observations and adds explicit evaluated-domain metadata for these references. The consumer rejects levels outside an attested domain. No broader monster casting or AI behavior was implemented.

Fifteen regression tests were added for descriptor/override/cap selection, zero level, separate instances, forged or borrowed UIDs, removed and foreign controllers, cycles, stale books, known-empty versus missing profiles, packet source identity, server critical/WP ownership and evaluated critical domains, and narrow compilation with grant permissions disabled. Syntax compilation passed. Automated unit/integration results are reported separately once the delegated validation finishes; the native book and critical checks do not prove effect execution, complete summon lifecycle, shortcut presentation, or connected-client acceptance. No service, Docker operation or database mutation was performed.

The dependency compiler now always includes the 297 newly imported class-summon definitions through an explicit scoped closure file. This does not enable temporary grants or import unrelated monster abilities. The remaining existing definitions in the full 623-effect transitive closure are supplied by the ordinary class, state and area catalogs. The first delegated focused batch passed 61 tests before this final compilation fix; its repeat remains pending and is recorded separately.
