# Native consume-resources family 923

`eXm` evaluates the AP and MP limits against the actual caster. A negative limit consumes all current points; a nonnegative limit takes the smaller amount. Its child is a fresh `eWf` action **30**, not an ordinary retained characteristic modifier. The constructor narrows each requested resource to a signed byte and clamps negative byte values to zero.

The implementation uses the actual transaction actor and native PA bounds/mutability. AP consumption calls the existing PA notification producer before MP consumption, preserving AP-to-MP listeners. The packed payment contains the points actually consumed, not the requested amounts. Neither runner enters the retained-effect population.

The child executes directly through `eZR.a(null,false)`, so it emits only post phases 3/4. Its constructor events are 0, AP 55 when requested AP is positive, and MP 65 when requested MP is positive. These bits remain unchanged when frozen PA consumes zero. The cancelled parent subsequently emits its own post phases 3/4. Zero actual payment suppresses application delivery but does not suppress post events.

The synthetic child has no PK or PL. Its native UID, base UID, generic reference and execution status are all -1; it has a default zero position. A narrow attested event-source contract accepts this constructor identity without relaxing ordinary owned UID validation. The unowned cvY13497 encoder sends the complete native proto without inventing an owned retention record.

## Evidence and validation

`sniffer/java/ProbeNativeConsumeAPMP.java` runs installed original `eXm.C`, `eWf.a` and `eWf.c` with original `fff` PA objects. Seven preparation rows cover min/all, zero, oversized limits and signed-byte overflow. Three original consumption rows establish actual AP/MP results and the executed-stage full proto. The private evidence is `.runtime/combat-review-20261007/consume-apmp-oracle.txt`; the source reconstruction is in `native-family923-cost-runner.txt`, `native-cost-Qe.txt`, and `spell-access-eZR-native.txt` in the same directory.

Four focused regressions cover the native rows, exact full application proto, post-event ordering, zero/frozen suppression and rejection of unattested synthetic identities. `PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_combat_consume_resources.py` passes all four tests. The actual bulk cast trace also exposed a null parent target: original `Qe.L` skips absent target delivery, while the synthetic payment remains self-targeted. The regression preserves these two distinct identities and the parent now uses the existing nullable-target lifecycle contract. A fresh bulk rerun is pending; this evidence does not establish whole Iop gameplay or client acceptance.
