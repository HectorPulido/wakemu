# Current user acceptance — 2026-10-09

## Socket bonus source correction — verified, not deployed

The user authorized the socket correction and explicitly prohibited restart.
The source now consumes common native Esquirlas27083, not bonus definitions;
uses the target item's level for bonus eligibility; treats unchanged late
confirmations as an authoritative refresh without another charge; and sends
BAGS13713 followed by native item-state13766 to refresh the open workshop while
preserving elemental selections. No gameplay state repair/refund was performed.

Luna's final targeted run passed28 tests with zero failures/errors/skips in
22.489seconds: test_socket_enchantment, test_socket_enchantment_concurrency,
test_socket_enchantment_wire and test_socket_enchantment_dispatch. SQL cases
used temporary schemas in wakemu_migration_test; the published runtime catalog
was read only. The initial run had two invalid concurrency fixtures missing a
required slot position; fixtures were corrected, preserving the production
validation, and the full targeted set was rerun successfully. The generated
13766 packet also passed the installed native Java decoder with sockets and
elemental state present. This is not a full-suite or visual acceptance claim.

The live server was independently observed as r61; these socket modules differ
from the corrected source. This review did not restart or deploy world. Retest
only after a separately coordinated full shared build/deployment. Previous
failed manual acceptance remains open until that acceptance passes.

## Failed socket bonus acceptance — Capa Jalosa

Hector reports ordinary socket installation fails manual acceptance. Before
reconnect the client repeatedly displays `Native socket bonus request contains
no changes`; after reconnect Capa Jalosa shows a blue elemental-mastery bonus,
but the native Esquirla reserve is unchanged and a comparison with another
unenhanced Jalosa shows no apparent stat difference. Do not mark socket bonuses
accepted from the persisted attachment alone.

Read-only request logs confirm one successful13269 request at2026-10-10
00:57:13UTC: actor6 inventory reference27094 decreased7→6, while reference27083
(Esquirlas) remained1. Subsequent requests were rejected without further
consumption. The prior manual command `!item 27094 7` incorrectly treated the
bonus definition as native currency. The server likewise aggregates consumption
by bonus reference. Currency mapping, immediate native UI refresh/no-op response,
bonus level eligibility and actual equipped-stat contribution require review.
No runtime correction or restart was performed for this report.

## Manual acceptance: contacts and ignored players

Hector confirms all five review steps work perfectly: adding a contact survives
reconnect; private messages arrive normally; ignoring the sender blocks delivery;
the ignored entry and blocking survive reconnect; removing the ignored entry
restores private-message delivery. Contacts and ignored-player behavior under13
is manually accepted. This test does not cover DND or remaining guild/intergame/
admin/political/PvP channels. Do not request these five checks again.

## Follow-up: late spectators, identification and passport

Hector assigns shared-combat acceptance step1 to another agent; do not duplicate
that work in this review. Late spectator entry still fails: the observer cannot
see summons, beacons and similar actors, and can become blocked. This report
specifically concerns observers arriving after combat has started. Defeated mobs
disappear for everyone and observers receive no rewards; both paths are accepted.
Keep late snapshot actor/effect publication and blocking open under16.

Identification works according to Hector. Socket/enchantment operations have
not been tested and remain pending under22; visible sockets do not establish
that their modification, costs or persistence work. Do not treat the acceptance
of identification as acceptance of socket operations.

Passport acceptance under24 failed: Hector still sees an Amaknian passport.
The source's neutral serialization and historical codec tests do not establish
correct live presentation. Keep the visible passport defect open.

## Follow-up: Haven Bag room access still blocked

Hector clarifies that the guest cannot move into the other Haven Bag rooms
during review acceptance step2. The owner can move between rooms. Everything
else in that journey appears to work.
The supplied screenshot shows a wheat-seed gathering tooltip with the explicit
native error `Esta sala está inaccesible`. Keep room traversal/access open
under26 specifically for guests; owner traversal is working. The user
clarification establishes the blocked actor as a guest. The responsible
permission rule and a server-side rejection remain unconfirmed.
Record the remainder of the tested journey as provisionally accepted, without
inferring completion of untested chest, zaap or configuration features.

## Follow-up: mount zero stats, worktables and character deletion

Hector reports an intermittent failure when equipping or unequipping the
Dragopavo: character characteristics become zero. Leaving and reentering, or
changing spells or characteristics, restores them. Track this as an open
mount/equipment characteristic synchronization defect under39/E17 and34/17.
This observation does not establish whether authoritative server values or only
client presentation are affected. Mount-system acceptance remains incomplete;
previous feeding and low-level scaling acceptance does not close this defect.

Hector confirms worktables (review acceptance step4) are resolved. Accept the
worktable scope under30; this confirmation does not independently establish
all Zaap travel behavior under35 or visitor workshop permissions under26.

Hector confirms character deletion (review acceptance step5) works perfectly.
Close issue38 as manually accepted. No runtime changes or restart in this review.

## r58 Tofullero acceptance failed

Normal entry still leaves the party blocked at the gate, with the initial group
behind it and Tofu Real included. User explicitly rejects the current first
encounter as the final boss rather than the first room. Reopen initial anchors,
reachable mob placement and native room ordering/composition; automatic progress
cannot be accepted when the first combat cannot be reached. Do not repeat the
instruction to defeat that inaccessible group or count teleport bypass as
acceptance. [Dungeon report](29-mazmorras-e-instancias/ACHIEVEMENT-AUTHORITY-20261009.md).
Jalató's earlier acceptance is unchanged. No runtime edits or restart.

## r58 beacons and late spectator follow-up

Fight110: Hector creates Cra beacons before Iop observes; observer sees player
and monster but no beacons. Attacks do not activate/explode beacons; direct
monster kill and zero-position checkpoint complete. Server has two added actors
while spectator snapshot repeatedly rejects remote-effect container absence.
The120-second external waits profile covers this reproduction. [Evidence and
separate open defects](../reports/health/BEACONS-LATE-SPECTATOR-20261009.md).
No code changes or restart. This does not close beacon activation or late-join
publication, and does not reopen accepted ordinary reward/mob-cleanup paths.

## r58 Haven Bag acceptance and access follow-up

Hector confirms account-wide bag sharing, another character entering, and
persisted decorations rendering correctly. Accept these observed paths. The
other character cannot leave the initial room or use the herbalism cauldron.
The screenshot shows native `Esta sala está inaccesible` on a garden interaction;
room authorization/configuration may explain the workshop restriction, but this
is not yet established. Keep visitor room access and workshop-use permissions
open and distinguish same-account owner access from foreign-account visitation
when correlating sessions. Do not reopen accepted decoration persistence.

Follow-up: Hector describes the blocked actor as another distinct character;
this does not yet unambiguously establish same-account versus foreign-account
ownership. The management console opens gem layout and craft-price dialogs,
but its central option does not open. Visitor-permission UI is therefore not
available to complete the suggested access test; do not ask Hector to configure
permissions through that missing UI. Gem/pricing dialog visibility alone does
not validate mutation/persistence or visitor workshop authorization. Screenshots
show the expected console, gem layout and craft-price window; the exact central
control's native action must be established from protocol evidence.

Remaining requested bag checks: central configuration/permission action, access
configurations for other players, bag zaap, and account chest. None are accepted from the entry/decorations test.
No runtime changes or restart for this feedback.

## r58 mount acceptance and multi-mount deletion failure

Hector's Audiluna screenshots confirm a new mount at level0 contributes0 mastery
before/after equip; after feeding to level2, both tooltip and character show1
mastery. Accept this observed low-level scaling path only. High-level scaling,
unequip bonus removal and persistence are not implicitly accepted.

A separate sequence with old/new mounts reportedly copied the old level onto
the new display, refused deletion, allowed one deletion, and left a mount absent
after reconnect. New visible UID1099511634091. Logs for actor1 show destruction
rejected at21:16:25.800,21:16:58.551,21:17:16.236 and21:17:23.897UTC because the
selected unit was considered equipped; one destruction committed at21:17:19.726.
The normal equipped-item protection is confirmed, but correctness of which UID
was selected/equipped is not established. No persistent XP duplication or missing
unit cause has been proved. Track multi-mount identity, active/other build links,
destruction feedback and reconnect inventory reconciliation as an open defect.
No runtime changes or restart for this review.

## r58 late spectator join feedback

Hector accepts defeated-mob disappearance in the first test. A second test,
joining observation after combat started, stalled temporarily and then completed.
Fight109 shows repeated remote-effect container snapshot rejections and a turn
synchronization warning. The external profile began after recovery and cannot
explain the earlier stall. [Incident and exact timeline](../reports/health/SPECTATOR-FREEZE-20261009.md).
Keep late-join synchronization and checkpoint freeze open; no runtime changes.

## r57 deployment and new HP feedback

Complete shared r57 is running; HTTP health passed and migrations085/086 applied.
See [release evidence](../reports/admin-chat/RELEASE-R57-20261009.md) for automated
gates. Source fixes do not close the reported live failures below. Both clients
need full relaunch for the new spectator/native pet hooks.

Hector reports momentary overhead HP-bar increases/decreases followed by normal
values. Captured PUBLIC_CHARACTERISTICS are removed in r57; remaining HP refresh
paths were audited: map snapshots are position-only, HP updates use owned state, and a serializer probe preserved injured HP300/max1050. No remaining captured-HP path was confirmed. This does not prove live flicker resolved; compare two clients during mount and bag transitions. Performance and checkpoint freezes remain highest priority.

## Latest r56 failures: checkpoint and Haven Bag

The global freeze remains open and highest priority. Hector reports a severe
freeze around bag reentry and then associates it with the save announcement.
Logs contain a 41.430-second global flush with zero persisted characters around
19:54UTC; logged SQL pool and Redis ACK stages were individually fast. Further
live thread/profiling evidence is required before attributing the entire delay.
Do not claim the previous lock fix resolved this incident.

Haven Bag exterior mobs are now accepted as absent, and gems persist across
reentry. Gem removal does not visibly return the unit until reentry. Decoration
and station learning works, but placement remains invisible despite green
preview; the first attempted cell becomes red/occupied and reentry does not
show the furniture. SQL confirms both placement commits, so render/publication
must be repaired rather than assuming rollback. Hector requests account-shared
bag state and an exterior entrance that other players can use to visit.

## Live r56 combat acceptance

Feeding follow-up: Hector accepts repeated feeding with the daily flag disabled.
The panel updates only after another interaction, so immediate refresh is not
accepted. Equipping/unequipping the mount shows excessive damage/stat bonuses
resembling maximum-level values; leveling the pet does not update character
stats. Reopen general equipment/client stat synchronization and XP-level source
validation. Do not mark mount stats or live refresh resolved from unit gates.

Hector confirms correct external sword placement, joining and spectating.
Participant A receives drops, XP and kamas; spectator B correctly receives none.
Terminal world synchronization still fails: after victory, the defeated mob
disappears for A but remains visible for B. Keep this cleanup defect open;
do not reopen already accepted basic joining, observation or reward eligibility.
Other r56 manual checks were superseded by the announced r57 restart.

## Live r55 acceptance update

Follow-up deployment: complete shared r56 is healthy. It includes fixes for the
reported gem recovery, exterior actors and furniture learning failures. Pet
feeding is repeatable with the database flag disabled; native XP scaling and
actor refresh are deployed. The client observer fix is rebuilt and requires a
full JVM relaunch. All reported failures still require manual reacceptance.
Sublimation installation fixes are included; combat effects are not activated.

- Chat commands and optional targets: accepted by Hector (steps 1 and 2).
- Identification: accepted; the new La Cola shows selected air mastery, no
  unidentified overlay, and three sockets. Sublimation functionality is a
  separate investigation requested by Hector, not implied by this acceptance.
- Shared combat/spectating/checkpoint and mount feeding: Hector is still testing.
- Haven Bag planting: accepted in garden rooms, rejected outside them.
  Gem removal/recovery fails, including a gem placed in an inaccessible slot.
  Exterior mobs are visible inside the bag. Using plush tofu or the portable
  herbalism workshop reports `Invalid native seed request size`; furniture
  placement and crafting are not accepted. General fixes are in progress.
- Optional future work: make monster reproduction inside private bags
  configurable through a database flag. Explicitly low priority.
- Feeding r55 follow-up: Hector fed the existing mount; level stayed stale
  until reconnect, then showed level 1. Log `2026-10-09T19:21:10.261702Z`
  confirms a committed, non-replayed +50 XP receipt. Live refresh still fails;
  pet characteristics remain unaccepted. A subsequent request at19:23:17Z was
  rejected by the daily UTC limit. Hector requests a database flag to disable
  this limit, disabled in this development environment, plus XP/stat validation.

This report records Hector's latest feedback. It supersedes older requests to
repeat the accepted basic interactions; it does not assert current full-suite
approval or deployment of concurrent source changes.

Deployment update: Hector explicitly requested deployment on 2026-10-09.
The complete shared checkout is now running as r55, healthy, with the furniture
catalog published. Marker positioning, checkpoint isolation, combined sockets
and element identification, feeding packet order/equipment refresh, and Haven
Bag extensions are available for manual acceptance. Mount stat scaling remains
open. See [chat commands and acceptance](../reports/admin-chat/COMMANDS-20261009.md).
The final r54 identification probe accepted the modal and changing to fire,
but found missing sockets and the unidentified overlay; r55 addresses that path.

| System / issues | Current acceptance and remaining scope |
| --- | --- |
| Performance 0 / E09 | **Highest priority:** Redis-to-database checkpoints reportedly stall the whole server and freeze fights for several minutes. Recurring user report; not resolved by earlier startup improvements or focused persistence gates. Measure and fix actual checkpoint contention. |
| Shared combat 14 | User confirms it works. External sword placement/visibility remains issue16. Do not request another basic joining acceptance. |
| Spectating 16 | Watching another player's fight still needs manual review. Source correction for sword centering is offline verified, not deployed by the marker investigation. |
| Haven Bag 26 | Gem assignment works. Persistence remains unaccepted/reported incomplete. Decorations, garden cultivation, and portable crafting require complete implementation and acceptance. Selling is optional, lowest priority. |
| Dynamic interactives 30/35 | User provisionally closes dynamic loading/interaction of dragoturkeys, dungeon entrances, etc., while retaining reservations. This does not close all dungeon entry criteria or interior progression. |
| Identification 22 | **Reproduced UI defect reported by user:** clicking does not display the identification modal; closing/reopening shows the item identified. A persisted mutation alone is not correct UI acceptance. |
| Builds 34 / equipment | Builds and many tested equipment behaviors work well. Equipment granting states remains explicitly excluded from acceptance. This is not universal equipment/modulation acceptance. |
| Exchange 11 | User requests closure: works well. Older partial-stack concern is not a reason to keep the accepted system open against this instruction. |
| Mount/pet feeding 39 | **Failed manual acceptance.** Client XP text appears but pet stays level0, food remains, and server rejects unstacked-unit validation. Unequipping prevents mounting until reconnect; expected characteristics are also reported absent. Investigation is active; this is not merely an untested feature. |
| Dungeons 29 | Jalató accepted. Tofulailler door passage and Miabuelita entry were reported separately. Installed configuration count is not a playable-dungeon acceptance count. |

Active delegated work: checkpoint freeze diagnosis/fix takes precedence;
Haven Bag implementation and identification UI follow separately. Preserve
combat/spells and concurrent edits. The latest explicit deployment instruction
superseded the older offline-only coordination restriction; root deployed the
complete validated shared image into the single world service.
