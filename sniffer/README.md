# Capture and analysis

Run from the repository root:

```bash
bash sniffer/build-capture-agent.sh
bash sniffer/decode-session.sh .runtime/captures/CAPTURE_ID
python3 sniffer/audit-capture.py --help
```

Raw captures stay in `.runtime/` because they contain private session data.
World loads its imported bootstrap records from PostgreSQL; it does not read
raw captures at runtime. Java exporters read the supplied client in `client/`
and write to their configured destinations. Use private `.runtime/` locations
for generated exports. The exporters do not request data from the official game
servers.

The launcher's historical authentication and capture scripts are research tools;
do not run them as part of normal local-server startup.

## Reusable sources recovered from local research

The project-owned `ExportSpells`, `ExportSpellCosts`, `InteractiveRegistryDiagnosticAgent` and `VerifyPatchedClasses` sources now live in `sniffer/java/`. Generated classes and exported client data remain private under `.runtime/`.

For the two spell exporters, supply the client directory and output explicitly:

```sh
mkdir -p .runtime/native-export-classes .runtime/native-exports
javac -proc:none --release 21 -cp 'client/lib/*' -d .runtime/native-export-classes \
  sniffer/java/ExportSpells.java sniffer/java/ExportSpellCosts.java
java -cp '.runtime/native-export-classes:client/lib/*' ExportSpells \
  client .runtime/native-exports/spell-data.tsv
java -cp '.runtime/native-export-classes:client/lib/*' ExportSpellCosts \
  client .runtime/native-exports/spell-costs.tsv
```

These exports support research and catalog reconstruction; they do not replace the complete database catalog import pipeline. See [protocol investigation and testing](../docs/protocol/investigation-and-testing.md).
