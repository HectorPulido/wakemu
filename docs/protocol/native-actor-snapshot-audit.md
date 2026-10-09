# Native fresh actor snapshots

`ExportActorCharacteristics.java` runs entirely against the bundled client.
It exports92 ffw definitions and2874 NPC profiles to
`server/protocol/native-actor-characteristics.json`. New ffh supplies current,
minimum (`aYW`, not `aYV`), effective maximum and fff.sfT freeze state. The
exporter also preserves hard bounds and expandability. Metadata comes from
native initialization, never synthetic universal zero values.

Native bjo allocates ffh and its dpU returns eGE.pIq; eGE.bcL returns0.
Native eGj.bcL delegates to this profile. Therefore fresh player radius0 is
accredited. NPC profiles use the private actual bbo.b(aMb) converter, ffC and
ffx. Curves are anchored at cqN minimum level; float growth becomes double
before multiplication, d2i truncates/saturates, then integer addition wraps.
Radius is aMb.csa narrowed to byte, forwarded by blj to eGC.bcL. Native ffx
fixtures at minimum and maximum reference levels are included.

`combat_actor_snapshot.py` initializes once from these definitions. Player
bonuses use owned equipment and aptitudes through equipment_stats.bonuses;
unsupported effects reject the build. HP percent modifiers are validated using
effective_character at actor.effective_level; other percentage modes reject.
Live HP/AP/MP/WP and maxima override initial resources explicitly. WP is not
assigned a universal racial amount, and its explicit values must respect
native hard limits. NPC nonresource stats use the complete native curves.

An explicit empty running-effect set is required; states or an already
initialized snapshot reject rebuilding. `ActorSnapshot.install` rechecks
identity, live currents and maxima so a stale construction cannot install.
Handlers must continue mutating installed snapshots instead of resetting
from gear after every cast.

Scope: this supplies the fresh characteristic baseline before deck passives
or combat effects execute. It does not initialize passives, controller/type
properties, block outcomes, critical selection, direction guards or event IDs.
Native eGj.fqm also registers dependency callbacks (secondary derived stats).
The helper does not propagate those callbacks on subsequent mutations; such
characteristics require their corresponding audited runtime handling. Current
common damage/healing arithmetic consumes the primary mastery/resistance
stats exported here.

Validation: five Python tests pass, including comparisons of all92 fields for
more than2000 viable NPC maximum-level fixtures computed by native ffx;
owned amulet bonuses, native FEROCITY default3, no-effect armor/barrier/virtual
HP, live resource preservation, stale install and missing-context rejection.
No service restart or official connection occurred.
