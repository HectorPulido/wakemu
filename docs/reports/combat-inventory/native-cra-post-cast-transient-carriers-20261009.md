# Cra post-cast transient state carriers

The actual normal4820 regression previously expected states7758 and7793 to remain in the state ledger at level3. Both published definitions have duration0. Their original immediate children347094 and349856 apply persistent3430 and7792 instead, each with raw parameter pairs[state,0,0,10,-1,0]; parent level3 therefore produces child state level30.

Original `eZk.Ty` invokes `bbX`, then retains only when `fyW.gtL()>0` or `fyW.guH()>0`. `bbX` handles negative indefinite durations, conditioned on `fyW.cxj`. A zero-duration carrier without delay is instant, not a retained state. Original bytecode inspection: `/tmp/wakemu-native-eZk-summon-pipeline.txt`, Ty offsets5–44 and bbX offsets5–65. The shared `state_requires_retention` and ledger already implement this contract; no production ledger mutation was required.

The strengthened actual runtime regression requires state_applied events for7758/7793 with level3, duration0 and instantTrue; verifies their persistent children3430/7792 at level30; excludes the transient carriers and the unrelated7760 branch; and preserves the source ledger, packet delivery and active-cast context assertions. It does not replace failed assertions with a broad success check.

Luna's actual runtime inspection confirmed persistent3430 and7792 at level30 after the original350554→352071→352072/352074 path. This diagnosis is independent of the new Iop cast-boundary policy: the policy-enabled/disabled observations were identical. Automated execution of the strengthened regression is delegated to the existing isolated validation runner; syntax compilation passed. No services, live database or production state behavior changed for this correction.
