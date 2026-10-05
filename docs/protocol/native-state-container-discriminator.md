# Identidad del contenedor de estados en el cliente actual

La lectura del bytecode actual confirma que `eZR.G(int,long)` interpreta el discriminador **1** como un estado: busca el contenedor en los actores y recurre al catálogo de estados. El discriminador **3** consulta `PN.baf()` / `Qs.dm()` y obtiene una zona `faV`.

`fyW.aZY()` devuelve la constante 1. `fyW.cmZ()` devuelve el campo corto `eiA`; no devuelve una constante 3. Confundir estos métodos produjo una explicación incorrecta del discriminador serializado.

Fuentes inspeccionadas: `.runtime/local/native-eZR-current.txt` (método G) y `.runtime/local/state-ui-fyW.txt` (métodos cmZ y aZY). La auditoría de capturas oficiales `docs/reports/combat-inventory/official-state-group-packet-audit.json` también encuentra tipo 1 e identificador en todos los grupos 330 observados.

Implicación: la autoridad de estados y su serialización deben conservar tipo 1. Las zonas deben conservar su discriminador propio. No convertir automáticamente todo contenedor 3 a estado. La corrección del motor está en curso; esta evidencia no prueba todavía un icono visible ni el ciclo de aplicación/retirada en GUI.
