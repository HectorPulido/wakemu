# Native summon nonexecuting samples

The five dependency-preflight failures for 2559, 2637, 2561, 4476 and 4478
share original summon effects 267185, 267193 and 267209. Each uses reference
4784 and a level mode equal to evaluation level: positive sampled levels
produce `[4784, L, 0]`, while the separately sealed zero-level producer yields
`[4784, 0, 0]`. The latter was merged into the dependency sample union and
previously caused the entire descriptor-domain extraction to raise.

Installed `eZl.C` accepts -3, -2 and -1 as contextual level modes. Positive
values are narrowed to a native short. Other nonpositive modes log and return
before descriptor construction (offsets 227–249); zero does not mean a level
zero summon. Nested summon profiles propagate this dependency to 2561/4478.

The exporter now preserves these samples explicitly as `nonexecuting_samples`
with their full parameters, effect identity, mode, reason and native source.
Their definitions and dependency closure remain intact. Descriptor levels
contain only actual constructor outcomes. A profile with only nonexecuting
samples has an empty descriptor domain and `level_domain_exact: false`, so it
cannot become ready by absence of execution. Existing contextual-domain
uncertainty remains independently blocked.

Sixteen focused tests pass: three new mixed/all-nonexecuting/nested cases,
ten existing exporter regressions and three existing default-mode tests.
No existing test was modified. Private actual-sample witness:
`.runtime/monster-blocker-recovery-20261011/summon-invalid-mode-witness.json`.

Runtime `summon_specification` still rejects an actually invoked invalid mode;
this change repairs dependency-domain diagnostics, not that execution path.
No native replay, monster activation, catalog publication or service restart
is implied by this offline exporter change.

## Runtime no-summon notification boundary

Source audit proves that an actual invalid-mode invocation is not equivalent
to returning false from the handler. `eZl.C` first reserves `rGF` and computes
reference `aSg`, then returns before constructing `rHG`. Its `c` method sees
the null descriptor and performs no creature creation. Nevertheless,
`eZR.a` sets execution flag `rEj`, calls the generic `d` notification when
`rIW` is false, and finishes through `Qe.a`. `eZl.a(iP)` serializes the generic
running effect and reserved creature identity even without a descriptor.

The existing Python `summon_application` builds a full descriptor publication
and requires an actual `SummonSpecification`, properties and obstacle identity.
That codec cannot represent this native nonspawn notification without inventing
a creature. A separate source-qualified generic 307 notification/delivery path
and its observer phase proof are required before changing runtime behavior.
Reserved identities, completion phases and callbacks must remain native even
when no actor is constructed. Strict `summon_specification` remains unchanged.

An actual installed-Java probe now exercises effect 267185's level-zero
parameters `[4784, 0, 0]`. It proves one reserved UID, null creature descriptor
and property descriptor, no spawn from `c`, and preservation of the reserved
UID in `eZl.a(iP)`. Critically, full additional serialization through `Qe.b`
calls `eZm.zt`, which dereferences the null descriptor and throws the original
`NullPointerException`. There is no valid full summon packet to reproduce from
this native path. Native `eZR.a` catches notification exceptions before
continuing generic completion; the actual PR notification/suppression contract
must be established before introducing any runtime path or claiming packet
equivalence. A fabricated descriptor-free packet would not be native proof.

Private witness source and result:
`ProbeNativeNonexecutingSummon.java` and
`native-nonexecuting-summon-witness.log` under the recovery runtime directory.
