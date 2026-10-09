# Shared delivery ownership blocker

## Verified scope

The full active normal review contains 60 `Missing native delivery owner routing` rejections affecting 23 spells across nine classes. **All 60 fail on effect family 315**, not on 23 unrelated mechanics. The focused casting smoke contains 24 such rejections across 12 Feca spells; all likewise fail on 315.

The rejection occurs in `NativeRetainedRuntime.normalize_owned_delivery` after the area handler has produced a retained application. `native_owner_flags` reads `native-runner-registration-owners.json`; the row exists but `bbA` and `bbB` are null. The cast transaction then rolls back. This is missing extracted ownership metadata, not missing target coordinates or a failed group criterion.

## General extraction gap

`ExportNativeRunnerOwners.constant` accepts only exact `ICONST_0/1; IRETURN`. It rejects two other provable static forms:

- Transparent `ALOAD_0; INVOKESPECIAL parent.bbA/bbB; IRETURN` bridge methods. Seven registry entries lose otherwise literal constant ownership.
- Instance boolean field returns initialized by the registry's constructor configuration and preserved by cloning. Nine area runner entries lose their immutable configured ownership.

Of 318 registry entries, 287 have both literal flags and 31 are null. The null group consists of seven transparent wrappers, nine constructor-configured area runners, fourteen parameter-dependent runners, and one nonexecuting placeholder.

`eYQ.bbA` returns `pYi`; `bbB` returns `rGU`. Its default constructor initializes false/true; the three-boolean constructor takes argument two/three for these flags. `eYQ` cloning copies both fields directly. They are not changed by execution or reset. Native registry family315 uses false/true; family314 uses true/true. The flags therefore must come from exact registry configuration, not from a universal class default.

The offline [probe](../../../sniffer/java/ProbeNativeDeliveryOwnerDefinitions.java) verifies original prototype/`bbn()` clone agreement for every nonliteral static runner. [Results](native-delivery-owner-probe-20261007.csv) include all constructor-configured area families and transparent wrappers. This is evidence for extraction design, not permission to guess defaults for null entries.

## Repair contract

Extend the metadata extractor to prove exact boolean bytecode with recursive transparent-super delegation, or immutable constructor-configured field reads with exact registry prototype/clone preservation. Record the proof form and source method/field. Preserve null for unsupported dynamic methods; reject incomplete metadata where it is consumed. This repairs all runners following the same structural form without spell or family ID exceptions.

Parameter-dependent methods remain separate contracts: `eYg` uses raw `So(2)` for actor/cell, `eXR` uses raw `So(1)`, and `eYZ` uses the inverse equality rule for raw `So(1)`. They must be evaluated from complete native definition parameters, not from an unbound prototype. `eZN` throws and must stay unsupported.

For family315 the proved pair is `actor_mode=false, cell_mode=true`. Existing `normalize_owned_delivery` consequently uses the caster as observation and full owner when caster differs from target. This changes packet routing metadata; do not change area ownership, target selection, spell outcomes, or retention state to bypass the rejection.

## Validation and remaining scope

Regenerate metadata offline, verify configured and delegated entries against original prototype/clones, then rerun the same full normal audit and focused smoke. A disappeared delivery-owner error alone does not certify the resulting glyph, state, trap or summon lifecycle. Validate retention manager, subscription, packet owner/UID and later interaction/removal separately.

## Implemented general extraction repair

`ExportNativeRunnerOwners.java` now proves these structural forms without a spell/family allowlist. The immutable-field proof requires a private boolean field and scans every method of its declaring class: writes must either initialize it on the constructor receiver or copy that same field from the source receiver into a different clone receiver. Unknown instruction patterns remain unresolved. Each proven pair is also executed on the native prototype and its actual `bbn()` clone; disagreement aborts export.

The staged output contains 303 proven pairs, including all 287 existing pairs unchanged and 16 newly proved pairs. Fifteen remain null: fourteen definition-parameter-dependent entries and the nonexecuting placeholder. [Verification](native-owner-extraction-verification-20261007.json) records exact entries and source/staging SHA256 hashes.

```sh
TASK_JDK=$(/usr/libexec/java_home -v 21)
"$TASK_JDK/bin/javac" -proc:none --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED -cp 'client/lib/*' -d .runtime/local/range-oracle-classes sniffer/java/ExportNativeRunnerOwners.java
"$TASK_JDK/bin/java" --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED -cp '.runtime/local/range-oracle-classes:client/lib/*' ExportNativeRunnerOwners .runtime/combat-review-20261007/native-runner-registration-owners-proven.json
```

A small offline boundary check injected only the staged catalog into the existing loader: configured area flags, category modifier flags, subscribed/unsubscribed retained delivery selection and unknown parameter-owner rejection passed. The full cast audits remain necessary after integration.

No production modules, deployed protocol catalogs, Docker containers or world services were modified. The exporter source, new probe, staging metadata and documentation were updated.
