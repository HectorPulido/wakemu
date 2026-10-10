# Haven Bag furniture, gardening and portable crafting acceptance

## Delivery status

Current release: r56 includes the native learning/collection flow, removable
optional gem flags, and exterior scene cleanup. Fully relaunch the client and
use the updated journey below; the original r55 furniture flow failed manual
acceptance and is superseded by this release.

Update: the complete shared r55 image and furniture catalog were deployed on
2026-10-09. The journey below is now available for manual acceptance; previous
source-only statements describe the state before this release.

Hector accepted decorative gem assignment on 2026-10-09, but explicitly reports
missing or unaccepted persistence. First verify insertion → exit/reenter →
reconnect, and resolve persistence before this extension journey. The extensions described
here are source changes awaiting publication of the new native furniture catalog
and integration into the complete shared world image. Do not run this acceptance
against an older image and interpret unsupported actions as a regression.

The implementation consumes one real inventory unit when placing furniture and
returns it when packing. Garden plants reuse persistent flora growth and harvest
transactions in map 9, isolated by the owner's character instance. Portable
stations can be placed in any enabled room, matching the native category rules;
the crafting room is used in this test for clarity. Stations reuse native recipes, profession requirements, duration and rewards.
Sales are outside this delivery. Native catalog mapping, room policy and wire
evidence are recorded in [the implementation report](../../reports/haven-bag-native-furniture-catalog.md).

## Preconditions

Use an account already authorized for development commands. Learn the relevant
harvesting profession (profession 72 for thistle and the suggested craft step). Start outside
combat, with several empty inventory slots. Use your own Haven Bag.

Grant test supplies:

```text
!item 4263 1
!item 4266 1
!item 4264 1
!item 6293 2
!item 4275 5
!item 17419 1
!item 2504 5
!item 6363 1
```

The furniture catalog identifies 6293 as a plush tofu decoration (template 2770)
and 17419 as portable template 19548, native crafting definition 82. Thistle seed
4275 exercises ordinary herbalism. Item names shown by the installed client are
the authority for the UI labels.

## One complete acceptance journey

1. Enter the Haven Bag and install the decorative, garden and crafting gems in
   three different empty rooms. Each room must show its corresponding floor;
   each insertion consumes exactly one gem.
2. Use one plush tofu from inventory to learn it. The stack must decrease
   2 → 1 and the native furniture-learned notification must appear. Open the
   furniture collection and place the unlocked plush tofu in the decorative
   room. Its position must match the preview; placement consumes no second
   learning item. Rotate and move it using the native furniture actions.
3. Pack the decoration using its native removal action. It must disappear
   without refunding the consumed learning item. Place it again from the
   collection. Exit, reenter and reconnect: the learned reference and last
   position/orientation must persist, with one unconsumed learning item left.
4. In the garden room, select thistle seeds and plant an adjacent valid cell.
   The percentage must match the native garden-ground calculation. A successful
   planting consumes one seed and creates one plant; a failed roll must follow
   the same existing seed-consumption rule, without creating a plant. Wait about 30 seconds for
   ordinary growth, collect seeds where offered, then harvest the mature crop.
   Growth and inventory rewards must persist across leaving/reentering and
   reconnecting, without duplicate rewards. No plants may appear in another
   character's private Haven Bag. Planting in the decorative room must fail.
5. Leave one plant growing and try removing its garden room gem: the operation
   must be refused and both plant and gem must remain. Finish harvesting before
   removing that gem. Placing furniture on a plant must also be refused.
6. Use item 17419 once to learn the station, then place it from the native
   furniture collection inside the crafting room. Open it from a valid adjacent
   interaction cell. With profession 72 learned, craft recipe 2227 once: consume
   item 2504 ×5 and item 6363 ×1, produce item 8414 ×1 and credit the normal
   profession XP. Retry the completion/reconnect: no duplicated materials,
   product or XP. A station in another private instance cannot be used.
7. Pack and replace the station, then leave/reenter and reconnect. The station
   must remain usable. Physical inventory-backed furniture packing with a
   full inventory must be refused without losing the station; collection furniture packing needs no inventory
   slot and refunds no learning item. Finally pack both furniture items, clear the garden,
   remove the added gems and verify the physical supplies remaining.

## Current limits to record accurately

- A second simultaneous instance of the same furniture template is explicitly
  rejected. The native client identifies these actions by template ID; unique
  dynamic instance IDs have not been established. Different decorations and
  stations can coexist.
- Enhanced item-specific data unsupported by the minimal native furniture form
  is rejected before consuming the item.
- Native exported furniture footprints have no relative cells. Validation
  covers the origin cell and room floor; multicell visual overlap remains a
  manual observation.
- Sales/display inventories are not implemented by these changes.

## Automated verification — 2026-10-09

Luna ran 67 focused tests in 17.788 seconds: all passed, zero skipped. This
includes real PostgreSQL transactions in temporary schemas of
`wakemu_migration_test`, plus native catalog and dispatch checks. Coverage
includes physical inventory stack placement/packing, foreign ownership,
occupied cells, full-inventory rollback, garden planting → growth → harvest →
reentry, and gem rearrangement → save → reopen → removal. No services were
restarted. This verifies source behavior, not the current deployed image or
Hector's reported visual persistence failure.

```sh
WAKFU_POSTGRES_TEST_URL='host=127.0.0.1 port=15432 dbname=wakemu_migration_test user=wakemu' \
WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu' \
WAKFU_DATABASE_PASSWORD_FILE='.runtime/local/secrets/postgres-password' \
PYTHONPATH=server:server/tests \
/Users/hectorpulido/.pyenv/versions/3.10.13/bin/python -m unittest \
  test_haven_bag_transfer test_haven_bag_furniture_transfer \
  test_haven_bag_furniture_catalog test_haven_bag_garden_runtime \
  test_haven_bag_garden test_haven_bag_store test_haven_bag_craft_station \
  test_craft_dispatch test_craft_wire -v
```

The runtime database above supplies read-only native catalogs; all test-owned
state and migrations use temporary schemas in the separate test database.
Redis caching was not configured for this runner, so catalog reads used the
existing PostgreSQL fallback.

The gem rearrangement regression uncovered an actual durable inconsistency:
room layout moved the gem while `haven_bag_gems.room_index/primary_slot` still
pointed to its previous slot. The source now updates both in one owner
transaction, preserving UID and item options. This defect does not establish
that it was the cause of Hector's separately reported persistence problem.

## Live r55 feedback — 2026-10-09

Hector reports that planting works only in a garden room, matching the intended
native admission policy. He reports failed gem recovery, retained exterior mobs
and a seed-size error when using decoration 6293 or station 17419. Therefore the
previous automated tests do not constitute acceptance of those native UI flows.

Investigation confirms the furniture inventory use path is a learning action:
`13220` carries 12 bytes (`action_id`, `inventory_uid`), whereas seed actions
carry 20 bytes. The previous dispatcher treated all actions as seeds. Native
learning consumes one item and unlocks an account reference; later placement
from the collection uses `13826` with the template ID. Packing a collection
furniture instance must not refund the consumed learning item.

After the routing correction, step 2 above is replaced by: use the plush tofu
once to learn it, confirm the native learned notification and collection entry,
then place it from the native furniture collection. One learning item is
consumed; packing and replacing must not refund or consume another learning
item. Apply the same flow to the portable crafting station. The old direct
physical-item placement path remains independently supported.

A configurable database flag permitting monster reproduction inside the Haven
Bag is requested as a lower-priority enhancement. It is not implemented or
required for this correction; garden flora and native furniture/gem recovery
come first.

## Corrected native UI gate — 2026-10-09

After the live r55 failures, Luna ran 50 focused tests in 17.454 seconds:
all passed, zero skipped. Modules: `test_haven_bag`, `test_haven_bag_transfer`,
`test_haven_bag_store`, `test_haven_bag_furniture_transfer`,
`test_haven_bag_furniture_knowledge`, `test_haven_bag_furniture_catalog`.
The PostgreSQL journey now learns via exact short `cqd` action, places virtual
furniture via `crM`, packs it without a learning-item refund, reopens account
knowledge and replaces it. Wrong action and foreign ownership are rejected
without consuming an item.

The native Java oracle also passed with installed client classes, validating
`czi`/13247, `fvr`/13873 kind11, `cqd`/13220 12-byte learning and `crM`/13826
26-byte placement for the actual item references 6293 and 17419:

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local \
  server/tools/java/VerifyHavenBagFurnitureLearning.java
java -Djava.awt.headless=true \
  -cp '.runtime/local:client/lib/*:client/contents/bdata/*:client/contents/gui_jar/gui.jar' \
  VerifyHavenBagFurnitureLearning \
  .runtime/local/furniture-learning-13247.raw \
  .runtime/local/furniture-learning-13873.raw
```

Corrections require migration 083 and the complete shared image. This gate is
source/native-codec evidence, not a claim that r55 already contains the fixes
or that Hector has visually accepted them.

## Live r56 feedback and next source correction

Hector accepted disappearance of exterior mobs and gem persistence. Do not
repeat those basic acceptance probes. Reported remaining failures are immediate
inventory visibility after removing a gem, invisible committed furniture, and
lack of account-shared bags/exterior visitor entry.

Read-only inspection confirms both furniture instances were committed in SQL:
plush tofu template2770 at (1,10,0), workshop template19548 at (0,6,0). A red
occupied preview is therefore not evidence of rollback. Native 12187 loads room
contents but does not register graphics. The source now sends dynamic scene
entities through 13664, with unique instance UID separate from template ID,
and 13082 removal before move/rotation replacement. Native Java validation
covers both bAs decorations and bDc portable stations.

Gem recovery now sends 12451 acknowledgement followed by 12471 item insertion;
the acknowledgement alone only clears the room reference in the client.

Migration085 selects one stable existing bag per account, shared by account
characters, preserving physical UIDs and plant instances. Previous nonselected
character layouts remain archived durably rather than merging incompatible
occupied rooms. Exterior bag publication and foreign-owner entry are included
in the coordinated source delivery. No service restart is authorized by these
notes; deployment remains coordinated by the parent while Hector is online.

After integration, additionally verify: switch to a second character of the
same account and see the same installed gems/furniture; another account sees
the exterior bag while the owner is inside, enters when permitted, and cannot
edit the owner's gems or furniture. Remove a gem and verify it appears in
inventory immediately without leaving. Place the learned tofu and workshop
from the collection, verify graphics and native actions, reenter, and craft
using the visible workshop. Existing accepted mob clearing and gem persistence
need only be observed as part of that complete journey.

Focused r56-follow-up verification: Luna reports **37/37 passing tests** for gem
transfer, account-shared bags, furniture transfer/rendering, crafting stations
and exterior visitors after correcting obsolete test adapters and malformed
legacy shard fixtures. Native client oracles accepted decoration and workshop
scene entities and removal; the exterior oracle also accepted native owner,
position and appearance fields. Source is ready for coordinated full-image
integration with migration085. Visual acceptance of these new flows remains
pending.
