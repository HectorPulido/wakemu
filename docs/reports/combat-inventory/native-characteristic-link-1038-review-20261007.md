# Shared eWh1038 live characteristic links

Native family 1038 is eWh, a live characteristic link based on eWa and an eWi PA listener. Its implementation applies by runner family and characteristic contracts, with no spell or class ID exceptions. The two passive audit failures refer to this missing general mechanism; executing a one-time stat gain would not satisfy its native behavior.

## Native contract and actual probe

C reads source characteristic ID, destination characteristic ID, optional reverse flag (exactly 1), percent (default100), optional positive upper limit (default0), and optional lower limit (default INT_MIN). Both IDs resolve through ffw byte identity. In normal orientation, source PA belongs to the actual target and destination PA to the caster; reverse swaps them. eWa attaches the eWi listener to the source PA and invokes it immediately.

Each listener callback first removes its previous actual destination contribution, then reads current source aYS. It wraps source*percent as Java int and truncates division by100 toward zero, applies upper min only when positive, then lower max only when above INT_MIN. It applies that result through destination fff.nG and retains the actual clamped delta. Cancellation removes that actual delta and detaches the listener. Base eWa removal only performs cancellation when native Ty is true; permanent nonretained links can remain active without an owned removal record.

`ProbeNativeCharacteristicLink.java` uses actual eWh/eWi/fff and a native PV proxy. Initial source60/destination10 at50% produces40; source rises80→destination50; source falls20→destination20; cancellation restores10 and subsequent source changes leave10. All actual-client calls pass. Private output: `.runtime/combat-review-20261007/characteristic-link/native-proof.txt`.

Native eWh AdditionalDatas fields are reverse17, percent19, destination characteristic12, upper10 and lower20. The running amount remains the source characteristic parameter, rather than the current contribution. Bytecode evidence: `/tmp/wakemu-{eWh,eWa,eWi,fff,PA}-1038.txt` and `/tmp/wakemu-{il,ij}-link.txt`.

## Shared implementation and mutation bridge

`combat_characteristic_link.py` keeps live listener records as plain Fight data and wraps actual actor effect_stats in a dict subclass. Slot assignments and update preserve native callback timing: a changed source value synchronously recomputes links, including remove/add notifications through chained destination listeners. Existing source writes were inventoried in stat handlers/consumers and removals, characteristic-level groups, resource handlers, maxima/minima, parameter bounds, costs, turn synchronization, HUD, withdrawal and weapon update. No changes were made to those writers; they already update the shared dictionary or its update method. ActorSnapshot only replaces effect_stats during verified fresh initialization, before listeners exist.

This producer is deliberately limited to owned, non-resource, non-expandable fff characteristic snapshots with actual current/minimum/maximum and frozen authority. Resource links and expandable PA require separate native raw/resource notification contracts and reject explicitly. Dependency cycles reject rather than silently dropping callbacks. Actual changes are clamped and wrapped before being retained for cancellation. Multiple live contributions remain independent.

Factory registers the shared handler and verifies existing bindings. The stat removal router delegates eWh ownership to exact listener cancellation and emits 13560 with the original running payload. The handler emits the normal owned application; existing retained routing remains responsible for selecting its observation/complete wrapper. No conditions or targeting adapter files were modified.

## Transaction and checkpoint authority

The observable dictionary explicitly deep-copies its data and rebinds the Fight through the deepcopy memo. A regression changes a transaction clone's source and confirms only the clone's destination changes. The actual checkpoint _plain accepts dict subclasses and serializes only scalar entries; listener records remain plain and no callback/Fight object is serialized inside actor stats.

Production checkpoint recovery aborts interrupted fights; it does not reconstruct or resume a live timeline. This change therefore adds no fictional restore hook. A linked actor whose stats have become a plain dictionary rejects at the factory/binding boundary, rather than claiming it can recover missed prior source changes. Unlinked newly created actor dictionaries may be wrapped safely. Any future live restore must recreate listeners before the first mutation. Arbitrary manual dictionary replacement or mutation bypassing dict methods is outside the proven producer contract.

## Validation and remaining gaps

Eight focused tests pass: live source replacement/removal/detachment, reverse and cap ordering, clamped actual cancellation, signed arithmetic, frozen/unsupported resources, dependency and stale binding rejection, transaction deepcopy and plain checkpoint, and actual NativeStatHandler173 gain/revert plus generic removal routing and packet type. Command: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python -m unittest server.tests.test_combat_characteristic_link` (8 tests,0.394s).

Broader integrated factory/stat/retained/timer tests are delegated separately. Current support does not claim a complete implementation of every PA subtype, generic native Qe phases for eWh, cyclic listeners, arbitrary live checkpoint restoration, or actual client packet receipt. A successful passive install/cycle remains execution observation, not complete semantic or client accreditation. Further actual packet decode/apply and cross-client validation remain pending.

## Central retained ownership integration

The central retained wrapper previously rejected class 1038 before reaching the live characteristic handler. Its supported ownership-family list now includes 1038, using the existing generic stat record, native owner metadata, delivery routing and removal registry. Class 339 is also admitted to that wrapper; its separate area removal contract is validated separately.

`test_combat_characteristic_link_retention.py` uses the installed native retained definition with `owner_on_caster=false`, rather than inferring ownership from listener direction. The listener changes caster characteristic 103, while the actual retained manager is the target actor. The test exercises the real wrapper, central record and complete-population view, live source changes, removal and observer detachment, central cleanup and the manager addressed by opcode 13560. Level 200 is explicit so the native upper-bound parameter is 200.

Validation: `PYTHONPATH=server /tmp/wakemu-combat-review-venv/bin/python -m unittest discover -s server/tests -p test_combat_characteristic_link_retention.py` — 1 passed. This closes the central admission gap; it does not establish the full eWh Qe event lifecycle or verification in the game client.
