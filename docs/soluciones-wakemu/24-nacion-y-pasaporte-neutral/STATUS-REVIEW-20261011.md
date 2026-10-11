# Passport citizenship follow-up — 2026-10-11

## Current conclusion

The historical Amaknian visual failure remains open until a current graphical
acceptance. No additional server patch is justified by this inspection. The
current implementation already removes a concrete later carrier that the
October 9 neutral-bootstrap evidence did not cover.

## Exact native citizenship consumer

Fresh offline disassembly of the installed original `wakfu-client.jar` confirms:

- `cTg` binds the visible citizenship label to `localPlayer` / `nation/nationName`,
  its stamp to `nation/passportStampIconUrl`, and color to `nation/nationColor`.
- `bVq.getFieldValue("nationName")` queries locale category 39 using
  `bVr.Xt()`. The stamp path uses that same integer nation ID.
- `bjG.zm()` consumes the entity section `qZ.Wi` (`NATION_ID`). If it differs
  from the actor's current nation, it resolves `frp.sZy.XH(id)` and applies
  `frk.a(actor)`. Zero is a registered native nation; this path contains no
  conversion from zero to Amakna.
- `bVr.i(frk)` applies the underlying nation and notifies its nation observer.
  The separate ranking property `pvpLadderEntry.nationId` is not the label's
  binding and must not substitute for checking the visible citizenship.

These are observations of installed original bytecode, not client changes.
Private disassemblies are retained under
`.runtime/local/passport-consumer-audit-20261011/`.

## Later identity refresh is already corrected and deployed

The October 9 review established neutral nation in a received `12666` entity,
not in every subsequent identity carrier. Opcode `15548` carries native
`FOR_GLOBAL_TO_LOCAL_CHARACTER` format 22. A captured nation in that later
snapshot could overwrite the earlier owned bootstrap; therefore the old
neutral-bootstrap observation alone did not exclude this failure mechanism.

Current `wire.minimal_entity()` replaces format 22 nation with the selected
character's canonical `nation_id`, resets inherited government synchronization,
and preserves the separately constructed guild and PvP-money tail. Recognized
ordinary entity and character-list formats use the same canonical authority.
This is not a demonstrated historical root cause: the original affected session
has not been correlated with a later format 22 body.

Read-only inspection of the running World on October 11 confirmed this exact
format 22 replacement is already deployed:

- Container: `532d507ebddb7d537bc58eb919acbfaec03716e5cff41ae889c58996e2c7662c`.
- Image: `sha256:74d90f6cef80728886aa00733d2a5a889d749cded44d5bd13523b1cf51bda7c6`.
- Installed `/app/wakfu_server/wire.py` SHA256:
  `6bc50df2f97552d3520c8c68b230f2aa329bccd6915ee2bb7fbc8c7e72996594`.

Existing targeted regressions are
`test_global_to_local_snapshot_does_not_restore_fixture_nation`,
`test_global_to_local_preserves_citizenship_without_government`, and
`test_authoritative_nation_survives_all_owned_entity_formats` in
`server/tests/test_wire.py`. Their assertions include owned actor identity,
canonical neutral/enrolled nation, government reset, retained tail, idempotence
and malformed packet rejection. All three targeted methods passed inside the running World against the
installed serializer (3/3, 0.014 seconds). The test source was streamed through
standard input; no container or repository file was changed. Evidence:
`.runtime/local/passport-consumer-audit-20261011/deployed-wire-gate.log`.
The broad nation suite was not repeated; its existing 120-case gate is
documented in the nation framework report.

## Complete acceptance to close the defect

1. Log in with a character that has never enrolled in a nation. Open `/passport`.
   Its citizenship label must be **Ninguna nación** (locale `content.39.0`),
   rather than Amakna. Missing neutral artwork is a separate asset limitation.
2. Switch to an owned hero and back, then reopen the passport. The selected
   character must retain its own citizenship; siblings do not inherit it.
3. Return to selection, reconnect and repeat. For an explicitly enrolled
   character the passport must show that selected nation instead of neutral.
4. If Amakna is still observed, record character ID and the exact visible label
   and correlate the received `12666`, `13713` and `15548` bodies for that session.
   Do not infer the retained UI model from the first bootstrap alone.

Passport activation, citizenship points, government privileges and territorial
ownership are separate authorities. This report does not invent those systems
or claim their implementation from the citizenship label.
