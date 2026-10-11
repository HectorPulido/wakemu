# Native random combat border policy — 2026-10-11

The installed native area catalog contains103 `BATTLEGROUND_BORDER` prototypes. Selection must not draw from all prototypes: many encode boss-, breed-, state- or team-specific mechanics, empty visuals, lethal effects or dependencies not certified for a generic null-owner perimeter.

## Qualified pool

| Native area | Root | Native children | Verified generic behavior |
| --- | --- | --- | --- |
| 46 | 152027 | 3641 / 152028 | MP loss, once marker; existing accepted border |
| 48 | 177618 | 177619 / 177620 | AP loss, once marker |


Requested native resource losses are2MP (46) and4AP (48). At zero willpower the original generic loss formula halves these to1MP/2AP. Runtime behavior remains native; this policy only chooses the original prototype. Native effects, child order, criteria, timing, flags and probabilities are loaded unchanged from installed catalogs. Tests execute each added prototype through production area-event and generic effect handlers and verify once-only marker behavior. No native effect is synthesized.

## Durable selection contract

A configurable SQL pool selects one reference using uniform server randomness before initial publication. The default pool is46/48:50% MP-loss and50% AP-loss. Prototype194 is excluded: its original masks include10007, whose producer is not supported by the generic area event runtime. Its10001 entry branch is tested independently, but that partial execution does not qualify the complete prototype for random selection. The placement transaction stores its policy version, reference and full native prototype/closure SHA256. Every replay reuses and verifies that receipt; policy changes apply to future fights. Old frozen layouts retain reference46. Initial bootstrap, runtime constructor, join/reconnect/spectator snapshots and world markers must all consume the same frozen reference. Duels, dungeons and Rifts must use the same freeze boundary rather than choosing per player or per packet.

Migration131 supplies the default configurable pool46/48. Placement freeze now persists the receipt in the same locked transaction as its layout, returns `terrain_effect_id`, and validates it on replay. Dispatcher creation, rebuilt placement packets and shared join context now consume that field. Friendly duels also use it immediately after freeze. No deployment or graphical acceptance is asserted.

## Automated verification

Native AP-loss48 and existing MP-loss46 execute through production generic area/effect handlers. The source gate also passes native closure equality against the production compiled catalog, dispatcher AST pinning, receipt validation and unqualified pool rejection. Prototype194 entry10001 executes independently but remains excluded because event10007 has no supported producer.

The broad32-test run had26 passes and six failures/errors caused by its private migration131 snapshot retaining the obsolete three-reference default. The corrected SQL placement/duel rerun passes9/9 in95.079 seconds with131 migrations, exact current migration131 and `changed=[]`. These are separate gates; this is not a claim of one clean32/32 execution. Logs: `.runtime/local/verification-border-policy-20261011/tests.log` and `.runtime/local/verification-border-policy-20261011/placement-duel-rerun.log`. No production source change was needed for the stale private snapshot.

State: implemented and automatically verified; **not deployed; complete graphical session acceptance pending**.

## Complete installed inventory

Unqualified does not mean the original mechanic is broken; it means it has not passed the generic random-perimeter contract. Effect classes below are native class identifiers, not claims of semantic acceptance.

| Native border | Root effects | Classes in exported direct child closure | Pool |
| --- | --- | --- | --- |
| 44 | 3647 | 194 | excluded |
| 45 | 3640 | 300 | excluded |
| 46 | 152027 | 330, 400, 48 | qualified |
| 48 | 177618 | 330, 400, 55 | qualified |
| 194 | 177621 | 330, 400, 48 | excluded (native event10007 unsupported) |
| 301 | 61257 | 1, 25, 330, 400 | excluded |
| 303 | 62107 | 304 | excluded |
| 318 | 64920 | 830 | excluded |
| 319 | 66471 | 304, 330 | excluded |
| 362 | 68999 | 2, 330, 345, 402 | excluded |
| 364 | 69266 | 120, 25, 304, 330 | excluded |
| 367 | 69382 | 304, 330 | excluded |
| 378 | 114364 | 400 | excluded |
| 388 |  |  | excluded |
| 406 | 72205 | 304, 330 | excluded |
| 417 | 80143 | 304 | excluded |
| 420 | 80676 | 304 | excluded |
| 422 | 80859, 197261 | 194, 304, 330 | excluded |
| 423 | 240460 | 307, 330, 349 | excluded |
| 425 | 82575 | 304 | excluded |
| 431 | 82913, 82912, 82844 | 300, 330, 41, 90 | excluded |
| 452 | 84775, 84776 | 300, 304 | excluded |
| 460 | 85788 | 191 | excluded |
| 462 | 282200 | 1, 913 | excluded |
| 467 | 86513 | 304 | excluded |
| 477 | 87324 | 304 | excluded |
| 479 | 87443, 87452 | 304 | excluded |
| 491 | 88488 | 830 | excluded |
| 495 | 91086 | 304, 330 | excluded |
| 501 | 92060, 92058, 194076, 194077, 194078 | 300, 304, 330 | excluded |
| 508 | 92742, 94229, 101375 | 120, 25, 304, 330 | excluded |
| 509 | 92764, 92765 | 161, 2 | excluded |
| 511 | 93113 | 304 | excluded |
| 513 | 93218 | 304, 330 | excluded |
| 525 | 96500 | 304 | excluded |
| 547 | 95669 | 304 | excluded |
| 553 | 96026 | 304 | excluded |
| 561 | 182779 | 2, 259, 330, 400 | excluded |
| 581 | 99102, 99103 | 120, 90 | excluded |
| 583 | 99110 | 1 | excluded |
| 585 | 100318 | 330, 339, 345, 349 | excluded |
| 586 | 100513 | 330, 48 | excluded |
| 592 | 100682, 101268 | 304, 321 | excluded |
| 594 | 100975 | 400 | excluded |
| 595 | 101705, 101019 | 302, 321, 330, 345, 349 | excluded |
| 596 | 101870, 101076, 101871, 119887 | 304, 330, 400 | excluded |
| 608 | 102889, 102890 | 25, 4 | excluded |
| 621 | 105198 | 304 | excluded |
| 624 | 105352, 107880 | 315, 330, 349, 400 | excluded |
| 670 | 111625 | 830 | excluded |
| 676 | 112203 | 304 | excluded |
| 677 | 112212 | 304 | excluded |
| 732 | 117036 | 1, 330 | excluded |
| 733 | 117034 | 1062, 1063, 330 | excluded |
| 794 | 145006 | 161, 330 | excluded |
| 882 | 149140 | 830 | excluded |
| 883 | 149150 | 330, 90 | excluded |
| 909 | 152446, 152447 | 28, 302, 330, 349 | excluded |
| 928 | 153131 | 304, 330 | excluded |
| 935 | 153755 | 304, 330 | excluded |
| 943 | 155109, 155113 | 160, 161, 330, 400, 41, 48 | excluded |
| 968 | 163157 | 304, 330 | excluded |
| 1038 | 174176 | 28 | excluded |
| 1044 | 175967, 174934 | 302, 330, 349, 400 | excluded |
| 1054 | 176057, 176945 | 330, 400, 48 | excluded |
| 1060 | 176851, 176852 | 48, 55 | excluded |
| 1085 | 177639, 177646 | 304 | excluded |
| 1100 | 181032 | 917 | excluded |
| 1101 | 181035, 181036 | 176, 48 | excluded |
| 1104 | 181110 | 1063 | excluded |
| 1106 | 181794, 182524, 182357 | 192, 304, 330, 400 | excluded |
| 1117 | 183366, 183365 | 304, 400 | excluded |
| 1122 | 183841, 183838 | 321, 330, 400 | excluded |
| 1123 | 183904, 183905 | 321, 330, 400 | excluded |
| 1126 | 185278 | 304 | excluded |
| 1146 | 186369 | 25, 321, 330, 48, 844 | excluded |
| 1147 | 186365 | 321 | excluded |
| 1174 | 190665 | 304 | excluded |
| 1188 | 193795 | 304, 330 | excluded |
| 1195 | 232977 | 304, 330 | excluded |
| 1196 | 203576, 203577 | 2, 304 | excluded |
| 1207 | 233037, 233038, 233042 | 31, 330, 400, 55 | excluded |
| 1239 |  |  | excluded |
| 1251 | 238674 | 2, 330, 400 | excluded |
| 1297 | 248292 | 304, 321, 330, 400 | excluded |
| 1317 | 256346, 256347 | 321, 400 | excluded |
| 1339 | 265144 | 304 | excluded |
| 1342 | 265328 | 315, 330, 349, 400 | excluded |
| 1347 | 266163 | 830 | excluded |
| 1379 | 270743 | 830 | excluded |
| 1393 | 272342 | 2, 330, 402 | excluded |
| 1434 | 289682 | 1, 25, 330 | excluded |
| 1458 | 293271 | 28 | excluded |
| 1465 | 293956 | 304 | excluded |
| 1747 | 338961, 338943, 338946 | 193, 194, 304, 330, 400 | excluded |
| 1749 | 339371 | 304 | excluded |
| 1760 | 341944 | 28 | excluded |
| 1770 | 342495, 342498 | 304, 400 | excluded |
| 1834 | 376613 | 304 | excluded |
| 1882 | 383574, 383575, 383578 | 31, 330, 400, 55 | excluded |
| 1931 | 390081 | 2 | excluded |
| 2014 | 393709 | 830 | excluded |
| 2083 | 408695 | 193, 330 | excluded |

## Manual acceptance after complete deployment

1. Start several ordinary fights and record the displayed border variant. Hover the border and inspect its native tooltip: the selected original prototype must show its AP-loss or MP-loss behavior. The default draws are independent50/50; repeated variants are valid and alternating results are not guaranteed.
2. During a turn, record current AP/MP and willpower, then cross onto a border cell with enough resources. Verify the matching resource decreases. Do not require a fixed numerical loss if willpower or native modifiers differ from the isolated zero-willpower test fixture.
3. Trigger the same border again inside its retained once-marker window: it must not apply a second loss while that marker remains active. After the native marker expires, a later eligible trigger may apply again.
4. Have another player join the same fight. Both players must see the same border prototype and tooltip. Reconnect one player and confirm the same encounter still uses its original border; no new draw may occur.
5. Repeat the inspection, one crossing and participant/reconnect consistency check in one duel, one dungeon encounter and one Rift encounter. Each encounter may draw a different variant, but every participant and snapshot inside that encounter must agree.
6. Record fight IDs, selected prototype/tooltip, AP/MP before and after crossing, and reconnect result. A short streak of identical outcomes does not establish a random-selection failure.
