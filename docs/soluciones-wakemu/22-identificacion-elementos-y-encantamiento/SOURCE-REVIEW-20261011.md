# Enchantment source review — 2026-10-11

> Current release2026-10-11: complete shared World/AI/ecology/admin deployed and automatically verified. Migration123; stable window released08:07 UTC. [Deployment evidence](../../reports/SYSTEMS-DEPLOYMENT-20261011.md). Graphical acceptance remains pending; any earlier prepared/not-deployed wording below is historical. Native planting bonus stays disabled pending its separate native-display acceptance.


## Inventory corrections

The native request decoder already rejects a target UID used as its own
sacrifice before any database mutation; a new regression preserves that
existing protection. Reference-only sublimation requests now
select the first consumable owned copy in UID order, instead of failing when
the first matching stack is protected and a later eligible copy exists.

Both mutation and bonus-installation services now construct the equipment
registry response (13078) inside the inventory transaction, alongside their
existing authoritative inventory and item responses. The dispatcher must emit
this prepared packet. A serialization rejection therefore rolls back the
ingredient, common shards, local fee, item state and receipt together.

Dedicated PostgreSQL regressions cover self-sacrifice, protected first scroll
selection, and registry serialization rollback for both operation families.
These tests passed in the133-test integrated core gate, including native wire
responses, concurrent duplicate/reconnect receipts and rollback after rejected
registry serialization. Evidence:
`.runtime/local/verification-20261011-plant-socket-mount.log`. The dispatcher
emits the precommitted registry packet. Deployment and graphical acceptance
of these final corrections remain pending; a passing inventory gate does not
prove EPIC/RELIC or general sublimation combat effects.

## Implemented scope and remaining boundaries

- Identification and elemental selection have prior user acceptance.
- Socket count, color and order mutations, equipment sacrifice, ordinary bonus
  installation, BASIC sublimation installation/removal, ownership/build/trade
  guards, durable retries and explicit local costs are implemented.
- Ordinary bonus installation consumes native common Esquirlas (27083), uses
  the target equipment level for eligibility and applies supported passive
  characteristic bonuses through `shard_bonuses`.
- BASIC sublimation installation checks an enabled native pattern against
  contiguous ordered socket colors; white slots match any required color.
  A repeated identical attachment consumes no additional scroll. Removal has
  no refund under the explicit local policy.
- EPIC/RELIC attachment eligibility is implemented in the prepared migration124
  follow-up below. Graphical acceptance and coordinated deployment remain pending.
- Sublimation installation is distinct from combat execution. The source
  planner preserves parent equipment container identity/level and complete
  effect closures, but has no live initialization caller. Current owned combat
  initialization constructs its factory before class and aptitude setup;
  equipment roots cannot simply be appended to that factory after creation.
  Native ordering, a complete merged runtime catalog, owned attachment authority,
  full state-child coverage and transactional fallback remain required before
  claiming general sublimation combat effects. Unsupported states must not be
  represented as invented flat bonuses.

## Complete manual acceptance after coordinated deployment

1. Identify fresh eligible equipment. Confirm the question mark disappears,
   sockets appear and the selected elemental bonus survives reconnecting.
   Equip it and confirm the equipment window accepts the identified item.
2. On an unequipped socket item, record its tooltip, common Esquirla reserve
   and wallet. Run `!item 27083 100`, install an eligible bonus, and confirm
   the native reserve decreases by the selected amount. Bonus definitions
   themselves are not consumable currency. Confirm immediate item refresh,
   then equip it and compare the supported characteristic with the baseline.
3. Increase the same bonus. Confirm only the additional cumulative shard
   amount is consumed; reopen and reconnect, checking item and reserve.
4. Sacrifice a separate duplicate equipment item. Confirm only that duplicate
   disappears and the target receives the configured charge/slot/color change.
   Reopen and reconnect to verify persistence.
5. On identified blue/green/blue equipment, run `!item 27123 2` and install
   Topología II once. Expect one remaining scroll and unchanged socket colors.
   Reopen and reconnect: the attachment and remaining quantity must persist.
   Remove it if desired: the attachment disappears without refund.

This acceptance covers inventory operations and supported ordinary bonus
statistics. Sublimation combat effects remain outside its accepted scope.

## Special attachment follow-up: verified source, deployment pending

Migration124 is staged, not deployed. Independent root comparison verified all
348 target tuples against the installed native export, including item level,
category, rarity and JAR hash. The catalog adds32 EPIC and47 RELIC definitions
with empty native color patterns while preserving388 BASIC patterns.

Native `bqV.dHp` delegates special eligibility to `fpR`: EPIC uses rarity7
(the internal enum label is `RELIC2`), and RELIC uses rarity5 (`RELIC`).
This predicate requires an unstacked target but neither socket colors nor an
existing `fpI`. BASIC retains its contiguous ordered color contract. Existing
local ownership, combat/trade, unequipped-target, character-level and fee
policies still apply. A fresh special target receives a minimal shard state;
it does not acquire sockets or elemental selection.

Normal and special attachments occupy independent native fields24 and32.
Installation, replacement, replay, removal and serializer rollback preserve
that distinction atomically. The combined migration124/chat gate passed63/63
without skips. The native Java oracle decodes Python-produced13983/13793
replies, ProtoItem/reconnect payloads and BAGS legacy options for special-only,
coexistence and removal of either slot. Its special-only phase also checks
zero sockets and absence of elemental-selection field56. Source:
`sniffer/java/VerifyNativeSublimationAttachments.java`; private replay evidence:
`.runtime/local/sublimation-eligibility/native-response-oracle.log`.

Manual inventory references: `!item 10272 1` (EPIC level20),
`!item 24130 2` (compatible EPIC scroll), `!item 24309 1` (RELIC level50),
and `!item 14186 2` (compatible RELIC scroll). Keep targets unequipped and
unprotected. Check one-scroll consumption, native special attachment display,
unchanged elemental selection, reopen/reconnect persistence and independent
removal alongside a BASIC attachment. These checks do not establish general
sublimation combat execution; that boundary remains as described above.

## Exhaustive combat follow-up inventory

The [complete per-reference inventory](../../reports/sublimation-combat-inventory/README.md)
now replaces the unspecific “general sublimation effects” boundary with all467
scrolls,2,036 effects,289 states,88 classes, criteria and subscription producers.
It distinguishes existing dispatch routes from missing owned initialization,
missing roots, unsupported `HasWeaponType`, unresolved event producers and
unqualified runtime contracts. It is read-only implementation evidence; it
does not claim combat execution or acceptance.

### Staged owned combat preparation — 2026-10-11

An immutable enabled attachment authority and private transactional owned-item
helper now pass14 automated tests, including actual native Influjo27152 state
application (characteristic9 +6), parent PL identity and rollback. They have no
production caller. Native relative equipment/class/aptitude ordering and a
fight-pinned closure reused by every later runtime factory remain integration
dependencies. This does not close general combat sublimations or certify all467
scrolls. See the [inventory's staged integration qualification](../../reports/sublimation-combat-inventory/README.md).
