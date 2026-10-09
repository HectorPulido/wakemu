# Native target selector bits 44 and 46

The shared fcE selector now recognizes the last two flag bits occurring in the indexed native class graph. Bit 44 requires the actual target to be an eGj and rejects it when native dTE() is true. It is the complement of the summon predicate within the eGj domain, rather than a generic non-summon area/actor test. Combining bit 44 with bit 32 therefore rejects both summoned and ordinary targets.

Bit 46 requires the actual caster/source to be Qq and compares its direct bch() owner pointer to the actual target. It does not traverse controller, master or nested owner chains. The existing registered area context provides is_Qq and q_owner_id; no new guessed actor typing or owner producer was introduced. A known null owner rejects an actual target; a missing source owner remains unsupported. IDs stand for the resolver's existing unique native PV identities, not a new owner lookup heuristic.

The predicates are inserted in native order: bit 44 follows bit 32 and precedes 4096; bit 47 precedes 43, and bit 46 follows 43. The selected area still passes independent Qq bcR/bit51 filtering and faH filtering. Native faV/eHg condition typing remains a separate contract; these flags test eGj/Qq directly. ffU is a serialization enum and is not the target selector predicate implementation.

`ProbeNativeTargetAreaOwnerSelectors.java` invokes original fcE.j(...).a(target,source) using typed eGj/faX fixtures while isolating their audited methods. Four summon/owner truth combinations are checked against five single/mixed masks, 20 native cases with zero Python mismatch. Native nonfighter/nonarea type guards and null-owner rejection also pass. The native source is fcE offsets514–554 and835–876 in the private original disassembly.

Command: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_target_area_owner_selectors test_combat_effect_targets` —18 tests pass. Tests cover all four truth combinations, mixed masks, native type short circuits, known-null versus unknown owner, and independent area-retention filtering.

The complete `class-native-target-selector-contracts-20261007.csv` now recognizes all 108 indexed fcE mask patterns with zero remaining unsupported flag patterns. Three formerly unsupported masks cover six effect definitions: 185236;175729 and 175811;410160,410155 and411588. Evidence and native/Python/probe/catalog hashes are in `native-target-44-46-review-20261007.json`. This is flag registration and focused predicate validation, not complete actor/area producer coverage, guarded graph reachability, spell execution or client certification. Older compressed component reports and narratives retain their earlier 105/108 checkpoint until refreshed as a complete source snapshot.

No services, database, Docker or running client operations were performed.
