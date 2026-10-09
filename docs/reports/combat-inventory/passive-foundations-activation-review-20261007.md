# Complete passive lifecycle checkpoint

The [machine-readable batch](passive-foundations-activation-review-20261007.json) finished all 339 class passives with unchanged tracked source/data hashes. It uses each passive's legal minimum level, native Ready events, damage, turn acknowledgements, expiry and an own cast, entirely offline.

| Observation | Cases |
|---|---:|
| Cycle observed | 336 |
| Blocked | 3 |
| Installation observed | 337 |
| Activation observed | 28 |
| Incomplete traces | 0 |

All 17 previous Enutrof border-condition blockers disappeared. The remaining blockers are shared engine boundaries:

| Class | Passive | Level | Stage | Boundary |
|---|---:|---:|---|---|
| Zobal | 7096 | 20 | Ready | Native effect family 1038, reference 308162 |
| Zobal | 7111 | 85 | Ready | Native effect family 1038, reference 308172 |
| Sadida | 8152 | 10 | Own turn after NPC acknowledgement | HasState triggering actor selector, reference 379549 |

The previous checkpoint observed 319 cycles, 20 blockers and 27 activations. These counts describe the tested lifecycle, not complete passive semantics. Installation does not prove activation; an observed activation does not prove all conditions, combinations or client delivery. No gameplay verification is claimed and no service was restarted.

Command:

```sh
PYTHONPATH=server:server/tests WAKFU_NATIVE_AREA_CALLBACKS=1 WAKFU_NATIVE_GRANTED_CAST=1 /tmp/wakemu-combat-review-venv/bin/python3 server/tools/audit_passive_activation.py --output docs/reports/combat-inventory/passive-foundations-activation-review-20261007.json
```

Result: exit 0, 339/339 cases, source_stable=true, 140.813 seconds.
