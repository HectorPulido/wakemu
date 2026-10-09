# Native portal casting eligibility

`fee` and `fed` are original native class names. They evaluate portal casting geometry; they do not define an AP/MP/WP surcharge. Resource costs continue through their independent native producers.

The new `combat_portal_casting.evaluate_portal_casting` implements fed.bot's entry/exit population and fee.fYt/u/v/w predicates. It requires a complete active Qs population, captured portal affiliation, actual caster/target cells, exact minimum/effective maximum, complete QI.U obstacle identities and conditional/LOS callbacks. Unknown inputs reject rather than use walkability, guessed team/owner or a generic ray.

## Actual entry and exit rules

Only actual GATE type19 Qq areas with the caster's captured signed-byte affiliation and an empty/null native QI.U set qualify. The adapter supplies normalized complete empty sets for native null. A gate has point radius0 in the current registered native constructor contract. Entry distance uses ala.c, which computes Java-int XY subtraction/abs, clamps each axis at0 and sums with signed overflow. Requested z is not part of this distance.

Entries must lie within the inclusive minimum/effective maximum and satisfy native selected LOS and cardinal linear checks. Entry LOS selection is `fyF.a(container,caster,null,fight)`; entry linear selection is `fyF.b(container,caster,gateCell,fight)`. These selections are independent of the main spell's actual target contract. Actual LOS calls `fcr.a(fromXYZ,caster.bcK,toXYZ,QI)` even when the from cell is a portal. It uses the caster's height argument, not the gate's height.

No entries means no exits. One entry means every usable gate except that sole entry is an exit candidate. Two or more entries means all usable gates, including the entries, are exit candidates. Each exit records independent native failures:

- `twU`: selected cardinal linear check fails, selected using the actual requested target aBn.
- `twI`: aBn.cG XY distance is outside the inclusive range.
- `twG`: selected LOS with actual null target fails from exit to requested target.

Category `fyU.tya` is native ID15. In this special exit branch, distance greater than0 produces only twI; other exits skip linear/LOS/range checks. Consequently same-XY different-z coordinates satisfy the branch. Java overflow can produce a negative distance, which also passes the native greater-than0 test. aBn.cG does not apply ala.c's per-axis0 clamp.

fee.fYt means at least one entry. fee.fYu means some exit lacks twI; fee.fYv means some exit lacks both twI and twU; fee.fYw means some exit has no failures. `fcO` applies each result in distinct range/alignment/LOS fallback conjunctions; the module exposes these separate predicates instead of conflating them into one generic success.

## Validation and remaining integration

Eight pure tests pass. They cover sole/multiple entry populations, independent failure channels, category15 branch, occupancy/affiliation, native conditional targets, Java overflow and missing authority. Command: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_portal_casting`.

`ProbeNativePortalGeometry.java` calls the original ala.c, aBn.cG, fed.k, fed.al and fee aggregate methods. Differential comparison has zero mismatches across6,561 geometry cases,729 inclusive-range cases and585 aggregate failure combinations. Native category15 is reflected from fyU.tya. Evidence: `native-portal-primitives-review-20261007.json`, including Python/probe/output and client library hashes. Private oracle output: `.runtime/combat-review-20261007/portal-geometry/native.json`.

The differential proves scalar geometry and native aggregate predicates. It does not independently prove the complete fed conditional/LOS callback integration. The normal casting producer must reselect fyP for actual null/cell targets and bind the actual QI/fcr geometry. `fee.cXm/cXn` select entries/exits through Java HashSet/HashMap identity iteration. The pure module intentionally exposes populations and failures without inventing a selected portal identity; cast execution, portal traversal effects and delivery need their exact native selection producer. No services, client session, Docker or database changes were performed.

## Native consumer and execution identity follow-up

A complete class-file constant-pool method-reference scan of the original `wakfu-client.jar` records six classes referencing fee/fed or cXm/cXn. The only calls to fee.cXm/cXn come from `aVm`, a client spell action. `cap` and `caq` call the base aTM gate accessors and expose script functions named `getValidInputGatePosition` and `getValidOutputGatePosition`, returning that gate's XYZ for action scripting. `fcO` only uses fee configuration/legality predicates and clears the evaluator; it never calls those gate accessors or rewrites the requested aBn target. Evidence: `native-portal-method-references-20261007.json`, produced by `server/tools/audit_native_portal_references.py`. Native bytecode is private in `/tmp/wakemu-native-fcO-portal.txt`, `/tmp/wakemu-native-aVm-portal.txt`, `/tmp/wakemu-native-cap-portal.txt` and `/tmp/wakemu-native-caq-portal.txt`.

`ProbeNativePortalIdentity.java` creates32 actual native GATE823 clones and verifies that their hashCode and equals methods are inherited directly from java.lang.Object. It fills the real fee entry HashSet and exit HashMap and confirms cXm/cXn select their actual first qualifying iterator element. The captured iteration differs from UID sorting. Evidence and hashes: `native-portal-identity-review-20261007.json`. Native object identity hashes are not exported UID hashes, map positions, affiliation, owner or Qs insertion order. Therefore a plain server area snapshot cannot reproduce the client's ambiguous visual selection merely by sorting those fields. Unique qualifying entry/exit populations have an unambiguous choice; multi-candidate visual order needs the actual native collection identity/iteration producer.

This follow-up does not prove a server effect-cell remap, portal hop, facing adjustment or resource surcharge. Adding such behavior based on visual gate accessors would change the actual requested target without a native execution contract. The normal casting integration retains the requested target cell and evaluates the proven portal eligibility. Portal-related effects, states or transformations in individual native effect graphs still execute through their exact general effect mechanisms and require their own source evidence. No remapping shortcut or guessed Java identity order was added.
