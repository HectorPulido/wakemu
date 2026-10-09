# Current critical source for qualified state pairs

The shared ordinary resolver now passes the actual state effect definitions and the current causing critical branch to `state_child_variant_mode`. This supports the pair-qualified Wakemu policy without replacing native fyW.guW behavior: original selective states still read their carrier's actual rHA flag, and unpaired/mixed states retain ALL.

For a retained listener reacting to a Qe source, the current source's verified PK variant determines the branch (`bool(native_definition_variant & 1)`). A proved null source PK is noncritical. Missing source type/variant evidence remains unknown; it is a blocker only when the qualified pair policy requires a branch. Malformed typed evidence rejects. For an owned execution boundary without a Qe trigger, the resolver uses its already authoritative current `critical` argument.

This deliberately separates a current critical hit from the beacon or carrier's creation flag. Tests exercise both opposite cases: normal creation followed by a critical hit and critical creation followed by a normal hit. The actual ordinary resolution callback is tested using the published compiled native paired-root definitions.

Validation: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_state_critical_source test_combat_state_variants` passed 10 tests. No state-specific IDs or per-spell condition bypasses were introduced at the source boundary. Full native-class transaction verification is queued with the immutable validation batch. No services were restarted.
