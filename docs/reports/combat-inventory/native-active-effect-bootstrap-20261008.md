# Active running-effect bootstrap

The active session adapter previously returned the two-byte empty running-effect population. Native `cuV`/13912 is consumed by `cjW.b`, which calls `big.dU`; `big.a(bytes,true,null)` calls `dq`, replacing the actor's Qf population, then resets/replays its running effects. An empty replacement loses category-specific modifiers and temporary abilities even when the server retains them.

Active actor serialization now uses the complete native `eZU.fSp` contract. That method includes every retained runner and emits state carriers before ordinary runners. The existing complete retained registry validates ownership and exact current state/stat/group/area payloads. The serializer preserves each stored UID and payload, excludes removed records through the authoritative live population, and never executes effects or changes the fight. Placement and the Ready baseline remain empty before initialization.

This is an explicit server implementation choice using an installed native complete-snapshot contract. The unavailable original server's choice between `fSp` and exposure-filtered `mv(boolean)` is not asserted. Native temporary HashMaps use object identity hashes, so their internal partition order has no deterministic UID contract. The server preserves its actual retained encounter order within the required state-first partition; it does not sort UIDs.

Supported turn-based and indefinite effects have no realtime deadline and encode zero remaining wall time. A positive realtime duration requires an actual recorded wall deadline and an explicit current clock; the serializer rejects missing authority. No scheduler or expiry is invented. Registered class summons use their actual native positive-ID serializer instead of a player database lookup.

`ProbeNativeRemoteEffects.java` passed five checks against the original private `eZU` envelope writer, including payload lengths 0, 1, 255 and 32767, and its 50,000-byte empty-population fallback. This primitive probe does not prove complete client replay or live reconnect. Focused population, category, removal and repeat tests are coordinated separately with validation.

Private source disassemblies are `spell-access-eZU-native.txt`, `spell-access-eZV-native.txt`, `spell-access-eZR-native.txt`, `spell-access-cuV-native.txt`, `spell-access-cjW-native.txt` and `spell-access-big-native.txt` under `.runtime/combat-review-20261007/`. No services or database were changed.
