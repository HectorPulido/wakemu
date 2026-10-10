# Sacrier SAC-01: source-attested missing native state

## Finding and native contract

State759 is absent from the original installed client, not an omitted valid state definition. The original class graph marks `state:759` as `native_missing:true`; the sealed published `native-class-state-resistance.json` explicitly records original missing state IDs. Effects316596,316608,316615 apply759 from the Berserker3702 dependency closure.

Original bytecode evidence in `.runtime/local/state-carrier-source.txt`: `eZk.a` calls `fRb`, which calls `fyZ.aaz` on the packed state reference/level. A null original template makes `fRb` return false; `eZk.a` logs and returns null (offsets104–149). In `.runtime/local/native-state-application.txt`, `eWu.D` calls `eZk.a`, tests its result and returns immediately on null (offsets34–42). No carrier, state, state children, or carrier registration is manufactured.

The nondefault application-chance path is independently defined: `eWu.fNa` calls `fyZ.aax` and returns0 when the template is null (offsets53–78). The native `-1` chance sentinel bypasses that lookup, but subsequent carrier construction still returns null. A zero chance retains the ordinary inclusive bounded-draw behavior; it is not an invented guaranteed early rejection.

## General implementation

- `combat_state_resistance_metadata.native_state_absence_proven` recognizes only absent IDs attested by the existing sealed native provenance. It does not infer absence from a missing Python dictionary entry, invent a state definition, or special-case759.
- `NativeStateHandler._application_chance` uses the native zero chance for attested original absence while preserving the existing RNG boundary. It does not fabricate a resistance enum.
- `NativeStateHandler.apply_reference` returns false before carrier UID allocation, packet registration or state child execution for an attested absent template. The applicator lifecycle remains in the caller, including the ordinary runner phases.
- An unexported/unattested missing state continues to fail. Tests use999999 for that separate failure case. A malformed missing-state provenance list is rejected.

## Offline native verification

`sniffer/java/ProbeNativeMissingState.java` loads the real bdata state registry. Native759 lookup is null; native `eZk.a` returns null at levels0,1,20,200,245,250,32767. Native innates3702 and4464 exist. Result: **PASS, seven carrier checks**.

Commands from repository root:

```sh
/opt/homebrew/opt/openjdk@21/bin/javac -proc:none -cp 'client/lib/*' -d /tmp sniffer/java/ProbeNativeMissingState.java
/opt/homebrew/opt/openjdk@21/bin/java -cp '/tmp:client/lib/*' ProbeNativeMissingState
```

Python compilation and `git diff --check` passed. The parent delegated fresh Python regression execution to Luna; record that result separately. No service restart, deployment, catalog publication or gameplay database mutation occurred in this task.

## SAC-06 grant and morph review

The current implementation already distinguishes ordinary owned spells, native raw-reference grants and temporary morphology books. Reviewed: ownership/foreign UIDs, maximum-level clipping, morphology level0, 80-object book capacity, existing raw object identity, grant expiry/removal, current-book removal semantics, packet application/unapplication and reconnect retained carriers.

The prior real lifecycle audit `native-morph933-lifecycle-review-20261008.md` naturally qualifies Venganza8587, installs profile5900, separately casts8588/8589/8590, verifies restoration and rejects foreign/expired UIDs. `test_combat_morph_spellbook`, `test_combat_spell_grant`, `test_combat_spell_grant_book`, `test_morph_class_dependencies` and `test_combat_heart_blood` cover related contracts. No new concrete SAC-06 implementation defect was established by this source review; fresh regression and real lifecycle execution remain required before expanding the coverage claim. No speculative grant/morph rewrite was made.
