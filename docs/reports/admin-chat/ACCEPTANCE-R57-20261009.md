# r57 complete manual acceptance

Prerequisite: fully close both client JVMs and relaunch with their usual profiles
using `bash client-tools/local-client.sh`. Reconnecting within the same process
will not load the updated native agent. Use separate accounts A and B.

1. **Performance and terminal synchronization.** Put A and B on the same map.
   A starts a fight; B observes using the sword. During a normal turn run
   `!checkpoint` from A and keep B interacting with the scene. Combat and walking
   must continue. Finish with A victorious: the defeated group must disappear
   for both A and B, while only A receives rewards. Reconnect B and verify no
   defeated group returns. A zero-position checkpoint validates the request,
   not persistence of a changed position and not resolution of the prior pause.
   If a freeze occurs, record its exact local time; the server now captures
   thread stacks for checkpoints exceeding five seconds.
2. **Mount statistics and HP stability.** Use the existing Dragopavo and grant
   wheat with `!item 18378 10`. Record mount level and character elemental
   mastery before equipping. Equip through the normal UI, confirm any build
   save prompt, feed repeatedly, then unequip/re-equip. Ref18682 uses floor(level
   *0.8): level8 gives6 mastery, level10 gives8. Check the *difference* from
   other gear, not total mastery. No captured 435 bonuses should appear.
   Feeding must consume wheat and update XP/level; inspect whether it updates
   immediately or only after another interaction. Watch overhead HP bars while
   equipping, walking, feeding and observing the other player. Record any
   temporary HP/max changes and the action that preceded them.
3. **Account bag, gems, furniture and visitors.** With A outside next to B,
   unlock the bag for everyone and enter. B must see A's bag at that exterior
   point and be able to enter using its normal action. Recover an empty optional
   gem: it must appear immediately in A's inventory; the fixed entry room and
   planted gardens remain protected. Learn `!item 6293 1` (Tofu plush) and
   `!item 17419 1` (herbalism workshop), then place their appearances through the
   decoration menu in an appropriate room. They must render, permit normal
   movement/rotation/packing, and survive reentry. Existing learned appearances
   need not be learned again. Test workshop interaction. Switch to another
   character of A's account: the same bag layout and furniture must remain.
   B must see the furniture but cannot edit A's bag. B exits to B's exterior
   position; A exits and its exterior bag disappears. Garden planting was
   already accepted; confirm existing plants survive this account switch.
4. **Dungeons.** Group A and B; run `!tp 527 -128 -33 0` on each. Enter
   Tofullero through the normal entrance. Defeat the entire eight-monster first
   encounter and return all fighters to exploration. The party must advance
   automatically through the rooms and exit after the final victory. Visual
   interior doors are disabled by the installed local policy. Native ordering
   and composition are not claimed faithful. Approach Casa de Miabuelita on
   map527 and try its normal entrance: missing achievement authority must no
   longer block an ordinary local character. Check Jalató entry/progression/
   exit for regression. Sorciere/Wagnar HasState requirements remain pending.

Already accepted: chat commands/targets, identification with sockets, sword
position, joining and observer reward exclusion. Do not repeat their standalone
probes unless a regression appears. Sublimation installation may be explored
separately (`!item 27123 1`, TopologíaII for blue/green/blue sockets); combat
bonuses are still pending and must not be considered accepted from installation.
