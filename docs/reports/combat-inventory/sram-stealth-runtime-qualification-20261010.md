# Sram stealth: bounded native lifecycle and remaining reveal boundary

The actual PostgreSQL state 3129 owns property 5 through effect 120855. State duration is two caster-end clocks. Effect 121382 separately installs property 54 with a one-end timer. Therefore property sets `[5,54]` immediately after Invisibility and `[5]` at the next owner turn are consistent with those distinct native lifetimes; they do not by themselves demonstrate a defect.

The post-cast listener 120857 subscribes to 1015/1025 and requires `not IsActivatedBySpell(4604)`. Its branch 136486 → 136487 → 120858 ends in family 402 with particle-system action 78902. It is a location/visual branch, not a state-3129 removal effect. The actual 4579 attack trace executes this branch. It is incorrect to infer that completing this particle must clear property 5.

There are separate native removal branches. Listener 120860 subscribes to 1014/1024 and installs cost-level group 410579 (family 912), subscribed to event 2234. It can install 411072, whose ordinary-damage subscription executes 411073 (family 321, removing state 3129) when `not IsTriggeredByIndirectEffect()`. Sibling 255663 has its own 1015/1025 removal mask and 2224 subscription. These conditions and subscription channels cannot be replaced with an unconditional attack-removes-invisibility rule.

The current server payment producer explicitly does not produce native special `mh/mi` events including 2234 (`combat_cost_payment_events.payment_event_ids`). A complete qualification of this particular damage-reveal path therefore needs the actual original caller that enables the special payment event, or an explicitly approved server policy with equivalent source context. The current ordinary-attack report cannot certify it.

The maintained actual-runtime harness asserts installation of both properties, committed enemy attack with completed 120858 child, expiration of property 54 after one real end/ACK cycle, and expiration of state 3129 plus property 5 after two real cycles. It changes no states, resources or clock counters directly. Passing these assertions certifies this bounded lifecycle only. Enemy-client visibility, movement disclosure and the conditional damage-reveal branch remain separate acceptance requirements.

## Paid-ability producer update

The shared server now has an explicit `PaidAbilityPolicy`: actual normal paid casts and paid family-426 casts enable native `mi` payment events, including 2234 for positive AP cost. This is a named Wakemu caller policy; it does not claim recovery of the unavailable original server caller. Generic resource effects retain their original fresh defaults.

The maintained Sram harness now separates two independent branches from the same actually committed Invisibility state. The quiet branch advances two real end/ACK cycles and checks each native expiration. The attack branch commits the real 4579 request and requires completed children 410579 → 411072 → 411073, followed by absence of state 3129 and property 5. This replaces the earlier observation-only attack qualification. The post-cast particle is not required in this branch: valid earlier state removal can retire its listener before the post-cast boundary. Terminal execution of the strengthened harness remains required before claiming this damage-reveal path passes.
