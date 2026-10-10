# AI catalogue inventory preparation

The external sampler found repeated `CompleteContextExporter._inventory_scan` / `register` filesystem work in NPC turn preparation. `NativeSession` calls `transport.catalog(exporter)` for each new owner turn; `turn_catalogue_scope` reuses the catalogue within that turn only. The receiver's manifest seal remains authoritative.

The exporter includes `catalog`, `engine` and the complete `server` roots. These intentionally overlap, so the same physical assets have multiple logical manifest entries. Before this change, each alias independently checked the source and cached snapshot. The cache index also checked identical content snapshots repeatedly.

## Narrow change

- Carry `DirEntry.stat()` metadata from fresh enumeration into registration instead of repeating `Path.stat()` for the source.
- Reuse physical source signature/snapshot validation only within one inventory scan. Preserve every logical alias entry.
- Reuse enumeration for identical roots only within that scan.
- Validate each unique content snapshot once while saving the persistent cache index.

Every subsequent inventory still enumerates the complete roots and observes newly created, removed, replaced and changed files. The source signature includes device, inode, size, modification time and change time. There is no TTL or cross-turn manifest shortcut. Database catalogue revision handling and receiver seal validation remain unchanged.

A global immutable-manifest cache is not safe under the current deployment contract: Compose mounts the SDK source directory into world from the host, so the container image identifier alone cannot identify all live source bytes. A future publication design would need an authoritative identity for SDK updates and database catalogue releases before replacing fresh inventory scans.

## Measurements

A read-only helper in the running world container imported the updated SDK and called `native_exporter().inventory()` twice:

| Measurement | Result |
| --- | ---: |
| First inventory (including cache preparation) | 1,225.376 ms |
| Warm inventory | 97.311 ms |
| Logical manifest entries | 18,381 |
| Content objects | 9,384 |

This measures catalogue inventory, not an entire NPC turn. It does not measure AI search, transport seal round trips, combat execution or client synchronization. It is not a before/after latency comparison and does not establish that all server delays are fixed.

A local synthetic case with 500 physical files and two identical-root aliases preserved all 1,000 logical entries, produced 500 content objects, and took a median 16.774 ms across five warm inventories. Instrumentation observed 1,004 `Path.stat()` calls per inventory after the change; `DirEntry.stat()` remains part of fresh source enumeration.

No game state, combat rules, spell logic, world process or service lifecycle was changed by the benchmark. The normal private catalogue cache was populated as part of preparation. Deployment and regression validation are tracked by the parent task.
