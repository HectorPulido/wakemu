# Legal class-passive mechanics audit

The new bulk gate plans **339 native optional passives across all18 classes**, each in a separate legal deck at its first legal passive level. It validates actual active-slot capacity and the single passive before production Ready. It does not build a Cartesian product of active/passive combinations. An optional upper-level pass adds level200 cases separately.

[Plan manifest](class-passive-mechanics-plan-20261008.json) and [typed native contracts](class-passive-mechanics-plan-20261008.json) preserve original selected spell roots, ordered effect children, possible native304 applied-state roots, criterion text, subscription/event fields, native masks/flags, raw parameters and original timing samples. State roots across native levels are a conservative dependency union; actual requested levels, stacking and guard execution remain runtime observations. Removal/criterion references do not execute the referenced state automatically. All339 planned passives have original root contracts; no missing applied-state export was found in this scoped plan.

The production audit uses actual Ready and Native RuntimeMessages. The fast gate selects at most two source-relevant owned actions and one actual Ready grant per case through the shared validator/prepare/commit path. Native parsed criterion AST literal spell references, exact subscribed elemental event IDs, and native child damage/healing families rank the owned representatives. Ranking does not evaluate guard truth or certify a requested context. All omitted references and unexercised requirements remain explicit. A fresh inspector per passive selects representative commits rather than suppressing them because a previous passive exercised the same family. Class/level source features are cached and runtime catalogs prewarm once. The current plan selects349 owned representatives across339 cases (329 cases select one,10 select two), with an upper bound of688 actions including one grant per case; it avoids the roughly6,000 repeated all-active transactions. Independent branches exercise owned client12161 movement with actual area movement callbacks, then real end/ACK/start and timed expiry. It records exact effect-reference ancestry, conditions/subscriptions, ordered state ledgers and packet/resource observations. Permanent passives are not forcibly removed, and missing summons, areas, thresholds or targets remain unavailable prerequisites.

The older published `passive-activation-luna-activation-01-20261007.json` contains337 observed cycles and2 blocked cases:7096/class14/level20 and7111/class14/level85, both with a stale PA-listener binding. That report disabled area callbacks;143 of its541 source identities differ from the current checkout. Its counts are historical evidence, not a current passing gate. The earlier336/339 estimate must not replace the exact report denominator.

Three pure tests pass: all339 planned decks satisfy production validation, state-removal references do not become state-execution edges, and parsed literal spell ranking ignores call-like text inside quoted strings. The optimized current339 runtime batch remains queued after a new frozen smoke; the older full-active loop must not be run as this gate. No full passive-mechanic or client percentage is inferred from the plan or a successful representative cycle.

```sh
PYTHONPATH=server:server/tools /tmp/wakemu-combat-review-venv/bin/python \
  server/tools/audit_class_passive_mechanics.py \
  .runtime/combat-review-20261008/passive-mechanics/current.json \
  --candidate-limit 16
```

No services, live database writes or client operations are needed for this gate.
