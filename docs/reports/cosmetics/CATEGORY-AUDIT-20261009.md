# Native cosmetic category audit

Costumes were manually accepted by Hector on r63. This follow-up is source-only;
no restart, deployment or runtime database write was performed.

The installed client exposes 1,234 `bIt` account learning actions. Learning and
selection are different operations: the common acquisition path already records
account ownership and consumes one physical item exactly once for these actions.
Selection must additionally populate the native preset and actor visual fields.

| Native category | Learning actions | Learning | Selection and visual synchronization |
| --- | ---: | --- | --- |
| 1 MOUNT_SKIN | 175 | Implemented | Source implemented; native PET projection, pending deployment/manual acceptance |
| 2 PET_SKIN | 262 | Implemented | Native actor/item application under review; selection rejected |
| 3 PLAYER_COSTUME | 562 | Implemented | Manually accepted on r63 |
| 4 PLAYER_SPRINT | 51 | Implemented | Source implemented; native actor sprint field, pending deployment/manual acceptance |
| 5 PLAYER_FINISHER | 36 | Implemented | Existing implementation preserved |
| 6 PLAYER_AURA | 127 | Implemented | Source implemented; native actor aura field, pending deployment/manual acceptance |
| 7 PLAYER_TITLE | 467 separate bIs actions | Source implemented | Native account title IDs, preset and actor title; pending deployment/manual acceptance |
| 8 PLAYER_HEAD_SKIN | 8 | Implemented | Native active equipment appearance component under review; selection rejected |
| 11 PLAYER_BACK_SKIN | 7 | Implemented | Native active equipment appearance component under review; selection rejected |
| 12 PLAYER_BOOTS_SKIN | 6 | Implemented | Native active equipment appearance component under review; selection rejected |

No `bIt` acquisition item exists in the extracted data for the other native enum
categories; that does not establish that those categories have no other source.

## Sprint and aura implementation

The native `pq.Tb/tF/tG` selected actor component already carries costume, hat
visibility, sprint, aura, title and finishers in that order. Sprint and aura are
native 32-bit item references, not custom entities or inferred animations.
`13765/col` now accepts categories 4 and 6 using the same account ownership and
exact operand validation as costumes. Each category holds one selected reference;
replacement, removal and preset activation preserve other categories. Selection
is persisted in a backwards-compatible `single_selections` record field.

`13873/eSX` includes the selected category positions. Actor refresh `13046` sends
the exact sprint/aura values to the wearer and peers, and reconnect builds them
from the stored account preset. Native cosmetic condition state also receives the
corresponding selected and active references, preserving existing finisher state.
Learning any additional cosmetic preserves all selected categories.

## Manual acceptance after deployment

Use an account that does not already own the items. With two clients on the same
map, run:

```text
!item 20820 1
!item 18299 1
!item 18300 1
```

These are validated native `bIt` items: Carrera de Ninja (category 4), Efluvios de
Stasis (category 6), and Decocción del tormento (category 6). Learn each using the
hand/use action; each physical item should disappear and enter the collection.

Select the ninja sprint in the appearance preset, walk far enough to trigger the
client's running animation, and compare from both clients. Select the Stasis aura
and then replace it with Decocción del tormento; verify the client applies its
native aura presentation on both clients. The costume and any finisher selection
must remain unchanged. Clear the sprint and aura, restore them, deactivate and
reactivate the preset, then reconnect. Selection and visible behavior must agree
on both clients throughout. Also repeat selection inside an owned or invited
haven bag and confirm that selection does not move the player out of the bag.

Aura activation/display timing follows the installed client. This implementation
does not invent a permanent effect when the native client uses conditional aura
presentation. Manual acceptance is required to establish that timing in play.

## Mount skin projection

Native `eSP.a(fvH,fC)` supplies the selected color and `eSP.b(fvH,fC)` supplies
an explicit accessory or the selected skin item reference. `ciu.ab` rebuilds the
mount presentation using its original definition, these visual operands, original
sleep state and health. The remote actor `rw/rz` carries those same operands.
The sixth `reskin_item_ref` integer is not applied by `bjo.b(rw)` and is therefore
not used as a substitute for the real visual fields.

Source now accepts category 1, persists it in the same generic singleton selection
path, and projects only `color_item_ref` and `equipped_item_ref` while encoding the
actor PET. The owned mount unit, definition, XP, health, sleep state and riding
state remain unchanged. Zero accessory values are omitted from the native `fC`
protobuf so the client can use its documented skin-reference fallback. Immediate
selection uses the existing complete PET publication followed by riding-state
restoration; reconnect uses the same actor PET projection. No new creature is
created and no mount statistics are copied from a cosmetic item.

For acceptance, use an existing equipped mount, or create a Dragopavo with
`!item 18682 1` and equip it through the inventory (native minimum level 35).
Run `!item 18708 1`, learn the appearance, then select it in the appearance preset.
Compare mounted and dismounted presentation from two clients, clear/reselect the
skin, deactivate/reactivate the preset, and reconnect. The mount's health, XP,
level and riding state should remain intact. Existing costume, aura and sprint
selections must remain intact. This test is pending deployment and user acceptance.

Companion pet skins (category 2) remain unselectable because this server currently
has no authoritative equipped companion-pet actor/state; presenting a skin as a
new pet would fabricate ownership. Equipment appearances require overriding the
remote actor equipment appearance section as well as the owner account preset;
that additional native path remains under review.

## Automated validation

Focused regression gate: 59 tests run, 58 passed, 1 skipped because its recorded
capture fixture is unavailable. The skip is the existing capture-dependent mount
publication check, not a new cosmetic test. The gate covers singleton selection,
replacement/removal, preset activation, costume/finisher preservation, malformed
and unowned requests, transactional acquisition and replay, persisted selections,
native PET projection and existing mount publication/codec behavior.

Modules: `test_owned_cosmetic_categories`, `test_owned_costume_cosmetics`,
`test_cosmetic_learning_postgres`, `test_owned_finisher_cosmetics`,
`test_combat_cosmetic_conditions`, `test_haven_bag_furniture_knowledge`,
`test_mount_codec`, `test_mount_publication`.

Native mount wire oracle: `VerifyMountCosmeticProjection.java` passed against
fixtures generated by the current Python `actor_pet` and `inventory_component`.
It decodes all six `rw/rz` fields through the installed client and verifies that
`fC` has the selected skin reference while the zero accessory is absent. Output:
`PASS native rw/rz projected skin=18708 definition=123 accessory absent`.
The authoritative test mount definition is deliberately preserved as 123; this
oracle checks the native byte contract, while visual rendering remains a manual
acceptance step after deployment.

## Follow-up full inventory

See `FULL-INVENTORY-DOFUS-AUDIT-20261009.md`, `inventory.json`,
`cosmetic-items.csv` and `dofus-named-items.csv` for all 16 native categories,
all 1,234 validated account cosmetic IDs, cosmetic-related non-bIt action items,
and all 42 Dofus-named Wakfu items. Native flag-35 audit identifies 127 cosmetic
auras plus 45 equippable aura items, rather than 172 equippable relics.

## Titles and emotes follow-up

Titles and emotes have dedicated native learning routes in migration 097. See
[TITLES-IMPLEMENTATION-20261010.md](TITLES-IMPLEMENTATION-20261010.md) and
[EMOTES-IMPLEMENTATION-20261010.md](EMOTES-IMPLEMENTATION-20261010.md) for
source status, native ownership contracts and complete acceptance procedures.
