# Captura y análisis

Ejecutar desde la raíz del proyecto:

```bash
bash sniffer/build-capture-agent.sh
bash sniffer/decode-session.sh .runtime/captures/ID_DE_CAPTURA
python3 sniffer/audit-capture.py --help
```

Las capturas permanecen en `.runtime/` porque contienen datos privados y algunas son fixtures necesarias para arrancar el servidor. Los exportadores Java leen el cliente instalado en `client/` y generan catálogos en `server/protocol/`. No realizan peticiones al juego.

Los scripts de autenticación y captura del launcher son herramientas históricas: no ejecutarlos como parte del arranque del servidor local.

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

These exports support research and catalog reconstruction; they do not replace the complete database catalog import pipeline. See [runtime portability audit](../docs/reports/runtime-portability-audit.md).
