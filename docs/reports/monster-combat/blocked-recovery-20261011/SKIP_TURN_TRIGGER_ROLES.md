# Native SKIP_TURN actors and triggered spells

Offline structural investigation; no activation, exclusion, resource changes or
runtime execution proof.

The sealed 808-reference blocked scope contains **two** actors with native fight
property 1 (`SKIP_TURN`): 4838 Concurso de belleza and 5661 Cristal eléctrico.
A name or SKIP_TURN alone does not prove an obsolete actor or encounter role.

## Representative 5661: exact native automatic trigger

Native descriptor levels: 248–253. Owned spells: 8298 División and 8299 Castigo
Celestial. Native initial states: 8649, 8640, 8650 and 8773, each level 1.

Initial state **8649** contains root **389435**, family 330, subscription mask
index 5 with bit **1001** (native start-turn event). Its own criterion is
`not HasWorldProperty(43, "target")`. It contains:

- **389437**, family **426**, parameters `[8299, 0]`, criterion
  `GetFightCurrentTableTurn() > 1`: invokes owned Castigo Celestial after table
  turn 1 through the ordinary triggered-spell path.
- **389436**, family **426**, parameters `[8298, 0]`, criterion
  `GetCharac("WP") > 0`: invokes owned División when the native WP condition holds.

This is direct native evidence of automatic dispatch. A validator requiring
normal tactical AI selection of both spells cannot establish the actor's
intended behavior. Granting AP, removing SKIP_TURN, or directly casting the
spells would change the scenario rather than validate it.

Other initial-state evidence: 8640 root389401 subscribes bit1003 and contains
family194 children; 8650 contains damage-bit2, KO1010 and regeneration1037
subscriptions; 8773 root392042 is family400. These source IDs are recorded
without inventing missing event authority or encounter properties.

## Appropriate future validation

Construct the native actor and its actual encounter participants through normal
initialization. Verify state8649 and its retained subscriber registration. Drive
the actual native start-turn boundary and table-turn progression through normal
fight lifecycle code, preserving SKIP_TURN. At table turn 1, prove8299 does not
trigger; after turn1, prove root389435 selects child389437 only when its native
world-property criterion allows it. Check native426 dispatch, real target
selection, packet/event delivery and effects. Test División separately with
actual native WP acquisition rather than injecting resources. Include negative
cases for world-property43 and unmet turn/WP criteria.

This plan needs real encounter context and runtime replay. It does not declare
5661 ready for generic wild-monster AI activation. SKIP_TURN does not by itself
prove that an actor's lifecycle start events are omitted; actual timeline and
dispatch behavior must be measured.

Concurso de belleza 4838 has no discovered initial-state family426 link to its
owned spells. Its role remains unproven rather than being inferred from name.

## General reusable audit

`server/tools/audit_monster_trigger_roles.py` audits any provided native scope,
walks initial-state child graphs, records subscription ancestry and criteria,
and links family426 constant positive finite integral spell IDs (zero level slope)
to actual owned spells. Unsubscribed owned trigger calls are reported separately
and do not establish a subscribed actor role. It separates the
first six PK subscription masks from index6 emitted bits. It preserves missing
state/effect diagnostics, bounds traversal and never changes runtime data.
State effect roots are structural unions; real execution must resolve the
actual descriptor-dependent state level before using them.

Private receipt:
`.runtime/monster-blocker-recovery-20261011/skip-turn-trigger-roles.json`.
Six focused pure tests passed, including emitted-mask distinction, missing
provenance, non-owned spell rejection, nonconstant/nonfinite spell slots and
unsubscribed-call separation. Source SHA-256 uses bounded streaming reads. Existing tests were not edited.
