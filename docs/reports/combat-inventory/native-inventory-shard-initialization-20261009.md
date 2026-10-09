# Inventory bootstrap failure on required empty-socket fields

The client log at local17:05:59.041 fails decoding cxC13078. The first failure is not a missing inventory handler: `hR.aU` calls `AbstractParser.checkMessageInitialized`, then protobuf attempts to describe missing required fields through reflection. The obfuscated class lacks the unobfuscated `getItemsList` accessor, masking the original initialization failure with a reflection exception.

Original `kX.isInitialized` checks every present shard message. Original `lD.isInitialized` checks each repeated `lK` socket. `lK.isInitialized` requires both `Ly` and `air`; `lK.writeTo` identifies these as field10(position) and field11(attached-item reference). The server's `_shard_state` emitted only field10 and field12(color), omitting the required empty-item reference.

The new producer emits explicit field11=0. The shared outgoing `initialized_wire_state` adapter also completes previously persisted empty sockets before sending ProtoItem.shard in13078 or the13766 response. This preserves stored bytes and the equivalent legacy equipment option; no inventory or database mutation occurs. It only fills an absent reference when shard quantity is absent/zero. An occupied socket with a missing reference or any socket with a missing position remains invalid. Complete sockets remain byte-exact and unrelated/unknown fields remain present.

Changes: `items/inventory_shards.py`, `items/shard_identification.py`, `items/shard_identification_wire.py`. No protobuf reflection bypass, equipment reset, client restart or deployment was performed.

Actual original-client parser proof: a small64MiB JVM fixture called `hR.aU` on the old slot(10=0,12=3), reproducing exactly `Generated message class "hR" missing method "getItemsList"`. On the same owned item with explicit11=0, `hR.aU` succeeded and `isInitialized()` returned true with one item. This independently identifies the masked initialization failure; it does not bypass native protobuf checks.

Automated focal validation (delegated): `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_inventory_shard_initialization test_shard_identification_wire test_shard_identification` discovered14 tests:6passed and8isolated PostgreSQL tests skipped because no test DSN was configured; no database connection was made. Existing wire/receipt fixtures now include the native required empty-item reference. The actual original-client parser proof above passed separately.
