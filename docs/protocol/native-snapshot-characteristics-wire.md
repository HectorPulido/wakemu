# Characteristics serialized from installed snapshots

Native tA writes an unsigned-short count and one tB per characteristic.
tB fields are: native PC byte, raw current bqD, raw minimum bqF, raw maximum
bqG, maximum percentage modifier sfV. The final integer is not a flat mastery
bonus. ffh.b(tA) reconstructs these fields; fff.aYU computes maximum using
Java signed-int multiplication/addition and division toward zero, then clamps
against the native hard bounds.

combat_snapshot_wire.snapshot_characteristics serializes all installed
characteristics. Player actual_actor_stats uses the same payload in both its
public and private sections; actual_monster_actor_stats uses it in the NPC
public section. Legacy serialization remains available only without a snapshot.
No equipment formulas are rerun on the snapshot serialization path.

Initialization preserves effect_percentages and effect_base_maxima, including
owned HP percentage aptitudes. A zero percentage is accredited by fresh native
initialization. For that case a subsequently changed effective maximum is also
the raw maximum. For nonzero percentages the serializer requires known raw
maximum metadata and checks that native recomposition matches the live effective
maximum. An unsupported percentage mutation rejects instead of erasing it or
applying it twice. Server current values are canonical clamped resource values;
hidden raw overflow values are not preserved by the current server model.

VerifySnapshotCharacteristics.java was compiled and executed offline against
Python bytes. Native tA decode and ffh reconstruction confirm HP80/max120 from
rawmax100/pct20, AP8/max9, WP3/max6, mastery125, virtualHP15/max30 and armor50.
Three wire tests check both player sections, NPC section, stale percentage
metadata and ordinary maximum changes. Existing actor and snapshot tests also
pass. No main receive handler, service, or official connection was changed.
