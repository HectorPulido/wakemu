# Competitive dungeon automatic modulation contract

## Native investigation boundary

The original investigation could not establish the official automatic stat profile. Lowering
only actor level would leave gear and aptitude allocations inconsistent and can
make current equipment validation reject the combat snapshot. A complete native
profile must supply the level, equipment, aptitudes, deck and resulting stats.

`characters/dungeon_modulation.py` reads the durable selection of the current
instance and active membership, accepting active/completed instance status until
return. It never changes the durable owned build selection.
Its native bands are 20, 35, 50, 65, 80, 95, 110, 125, 140, 155, 170, 185, 200, 215, 230;
it never increases owned level. Automated verification and transition publication integration remain with the coordinator.

## Original client and official capture evidence

The official 12666 capture from 2026-10-03 contains a default permanent sheet 0,
custom sheet 1, and permanent automatic sheets 2..10 at 20..140. Their names are
blank; field 56 is 0 rather than 1. Each automatic aptitude sheet contains only
field 24=level, with no allocated aptitude entries.

The same capture's 12393 equipment registry for actor 2409354 has concrete object
entries for sheets 0/1. Automatic sheets 2..10 contain only protobuf field 424=level
and no object entries. The actual reader `fpi.d(ia)` decodes this through
`ia.tL()` into `fpj.bz(short)`. `fpj.cmZ()` exposes that level; downstream `fop`
uses it for item-level validation. This reader does not generate equipment or
stat bonuses. The unrelated `fpj.giF()/no()` boolean bypasses validation during
local equipment preview/copy; it is not an automatic-profile flag.

`eQW.QW(level)` finds an existing permanent sheet at the exact level. It does not
create a profile. Current `items/builds.py:build_set` deliberately publishes only
locally owned/default sheets, excluding the other actor's captured templates.
There is consequently no locally initialized automatic profile to select.

Private decoded evidence is under `.runtime/local/dungeon-modulation-*`, notably
fixture builds/aptitudes and native `fpi`, `fpj`, `eQW`, `biB` disassemblies.

## Integration candidate and missing contract

A trusted temporary projection can select a fully specified owned permanent
sheet at the native band, pass its existing equipment/aptitudes/deck through the
same snapshot path, and restore the previously selected sheet on leaving. That
is coherent for an existing complete profile; it does not establish a default
automatic profile for every character.

The remaining native contract is the automatic profile's stat contributions:
which authoritative effects/characteristics the official server applies when
activating its empty equipment/aptitude automatic sheets, and their values for
each band. Neither empty protobuf section implies zero intended bonuses nor
justifies prorating equipped gear. A capture containing actual automatic-sheet
activation or the corresponding original template/effect catalog can resolve
this bounded gap. State names such as "Player characteristics" alone are not
sufficient: some candidates set unrelated fixed combat stats.

The durable difficulty selection and its cap are already authoritative inputs;
client packet values must never create or override the temporary profile.


## User-authorized custom automatic profile

Hector explicitly selected a custom server formula after the native evidence
boundary above. Migration 127 stores version 1 in settings under
`dungeon_automatic_modulation_policy`. This is local balance policy, with no
claim of matching official automatic modulation.

For `L=min(real character level, selected native band)`, the profile adds to the
native bare-character baseline:

| Characteristic | Flat addition |
| --- | --- |
| Maximum HP | `10*L` |
| Each elemental mastery | `4*L` |
| Each elemental resistance | `floor(L/2)` |
| AP | `1` at 50 and another `1` at 125 |
| MP | `1` at 80 |
| Critical chance | `floor(L/10)`, capped 100 |
| Initiative | `L` |

Breed WP and all other native baseline values are retained. Coefficients and
resource thresholds are validated server configuration. Individual owned gear,
aptitudes and their effects are replaced by the same profile for every
competitive participant; the actual inventory and saved metadata are retained.

Store hydration copies the owned snapshot, creates one temporary permanent
native automatic sheet in the highest free signed-byte index, and selects it
only in the returned snapshot. Empty automatic equipment/aptitude sections carry
the effective level using the verified native protobuf fields. Deck projection
retains legal existing spell choices and slot positions, clears locked spells
or slots, and caps their level without rewriting owned spell XP or saved decks.
`equipment_stats.bonuses` feeds the same profile to public characteristics,
combat resources, damage calculations and ActorSnapshot initialization.

The original durable active build and revision never change. Temporary build
saving, activation and deletion are blocked. Owned inactive sheets remain
editable. Reconnection derives the profile again from current membership and
persisted difficulty; leaving removes it without deleting or rewriting a sheet.

HP uses existing canonical wounds (`hp_damage`) and death state. Hydration
computes the temporary visible HP without writes; the coordinator's transition
boundaries must persist the reconciled maximum and reset regeneration in their
existing transaction. Returning computes the owned maximum using the same wound
count, so entering/leaving does not heal or erase damage.

Focused tests cover profile coefficients and thresholds, publication, legal deck
projection, actual native ActorSnapshot/public-stat agreement, isolated
PostgreSQL reopen/return restoration for two participants, and mutation guards.
Suite execution and complete entry/exit/hero lifecycle acceptance are pending
coordinator verification; this report does not claim deployment.

## Canonical health transition integration

`characters/dungeon_modulation_health.reconcile` locks the actual character rows,
derives each effective maximum through the same equipment/profile reducer, and
persists HP from canonical wounds/death. Regeneration keeps its rate while its
baseline and clock are reset when the visible maximum changes. Dead characters
always have regeneration rate zero. Automatic gear has no mount: riding ends,
while the owned mount unit and saved equipment remain unchanged; exiting does
not automatically start riding again.

The helper is called inside entry/movement, difficulty reuse, explicit exit,
automatic exit, stale recovery and generic `Store.transition_map` transactions.
A valid reconnect rebinds the durable same-account dungeon cohort, including
heroes, and reconciles its health before initial publication. Stale recovery
returns that cohort together to its pinned exterior. Live combat recovery does
not rebuild its running actor profile. The dispatcher must reload the selected
Store snapshot after recovery, including successful private-instance recovery,
and publish fresh owned hero snapshots rather than previously cached objects.

`test_dungeon_modulation_health_lifecycle.py` exercises real native competitive
entry with a main and owned hero, complete return restoration, entry callback
rollback, hero-in-combat exit rollback, reconnect cohort generation/HP repair,
stale-run recovery with death, and a generic return followed by an actual
canonical damage CAS. Execution is delegated to Luna; results belong to the
coordinator's final verification gate.
