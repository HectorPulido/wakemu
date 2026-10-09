# Complete class state gap inventory

Native state denominator: **764**. Status counts: `{'partial': 79, 'pending_verification': 682, 'absent': 3}`.
Native missing references: `[759, 7986, 8873]`. Tracked sources stable: **True**.

This is a state inventory, not a scenario count. No state is accredited as completely semantic/client verified.
`partial` means a concrete shared gap was found; `pending_verification` means local metadata/routes exist without full state behavior proof.
`absent` records missing native/local definitions without claiming the conditional branch is reachable. `broken` records native/local sample contradictions.

JSON preserves every state, native level group/container, class/spell reverse index, application effect, route gap, criterion and lifecycle dimension.
CSV provides one row per state. Rebuild with `python3 server/tools/build_class_state_gap_inventory.py`.
Native raw definition identities are checked before the build; this avoids mutable-loader record reuse corrupting the denominator.

| Lifecycle contract | Shared source and remaining limit |
| --- | --- |
| Application/levels | combat_state_handler, combat_state_parameters, combat_definitions; sampled native/local values compared per state |
| Accumulation/replacement/refresh/protection | combat_state_application; shared implementation, per-state sequences pending |
| Duration/expiry | combat_state_timing, combat_native_timing_context, combat_state_ledger; realtime scheduler and timed area clock reject |
| Retention/children | combat_state_handler/state_managers/subscription_runners; null Qf, instant subscribed children and missing subscription families remain guarded |
| Decurse | combat_state_decurse; selective beneficial child classification remains absent |
| Reset/withdraw/client reconnect | Pending per-state verification; a source route is insufficient evidence |

Every conditional path remains reachability-unknown. A missing transitive family can sit behind a false criterion; this inventory does not declare its owner class broken.
Manual acceptance templates accompany each row, but exact playable applicators and expected event conditions still require resolution before execution.
No services were restarted and no runtime catalog was mutated.
