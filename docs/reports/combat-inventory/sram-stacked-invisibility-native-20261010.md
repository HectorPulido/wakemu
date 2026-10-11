# Sram stacked invisibility: native removal qualification

This review found no implementation mismatch in the suspected removal path. It does not certify the complete invisibility lifecycle or client rendering.

Original client bytecode `eWt.bbR()` first invokes `PV.g(property)` at offset 26. For either invisibility property (`ffe.sdC` / `ffe.sdO`, IDs 5 / 18), it then invokes `QI.c(target)` at offset 137 and `QI.e(target)` at offset 148. There is no remaining-property-count check between decrement and either call. `QI.c` removes `target.bcN()` from `biN:TByteHashSet`; `QI.e` removes it from `biO:TByteHashSet`. These are sets, not reference counters.

Consequently, removing one overlapping invisibility effect retains the other property counter while clearing the QI exclusions. The current `remove_fight_property` behavior matches this native sequence. Adding a reference-count guard would change the recovered original behavior and is not justified by the reported suspicion.

The dedicated regression `test_sram_stacked_visibility_native.py` covers all four overlapping combinations of properties 5 and 18. It asserts both the surviving property count and cleared spatial exclusion sets, without changing production code. Validation is delegated to the coordinated test agent.

Evidence was read with JDK 22 `javap -classpath 'client/lib/*' -c -p eWt` and the corresponding `QI` methods. Private inspection outputs: `/tmp/sram-eWt-native.txt`, `/tmp/sram-QI-native.txt`.
