# Familia nativa 315: áreas de efectos

`eVi` registra 315 como `eYQ`, que crea un `Qq/faV` mediante `fbr/bcX → bcN → Qr`. No retira estados y no crea un actor `eHD`. Los registros de áreas pertenecen al gestor `Qs`, independiente de la iniciativa y de la lista de combatientes.

`eYQ.C` reserva un UID de área distinto del UID del efecto. Parámetro 0 identifica el prototipo; parámetro 1, si existe, es el nivel convertido a short, sin aplicar una limitación arbitraria; parámetro 2 igual a 1 mantiene el área cuando termina el efecto creador; parámetro 3 identifica una dirección `aAS`, y una dirección inexistente utiliza la del propietario o `NONE` si no existe propietario.

El escritor nativo usa AdditionalDatas: nivel14, dirección16, persistencia17 y UID21. El contexto `eVt` pertenece al campo13 de RunningEffect; el campo12 es otro mensaje. `ProbeNativeEffectArea.java` ejecuta el cálculo, escritor y decoder reales de `eYQ` y `cvY`. El paquete Python coincide byte por byte con el mensaje canónico nativo.

El catálogo `native-effect-areas.json` contiene 1.436 prototipos extraídos de los datos instalados y de la fábrica nativa. Los nombres `properties` y `characteristics` reflejan los getters originales ckD/ckE; no acreditan que su semántica coincida con las características de un actor. Se conservan también getters y clases originales.

El primer camino admitido es un prototipo `faZ` (hora) vacío, con forma `anD`, sin efectos ni máscaras de entrada/salida, y persistencia activada. Se valida por contrato del prototipo, sin lista de referencias de hechizos o clases. Las demás áreas se rechazan explícitamente hasta acreditar sus callbacks. Se mantienen UID, propietario, nivel, dirección y celda en un registro de áreas del combate serializable.

`Qs.a` rechaza UID repetidos y registra el área sin reemplazar actores. `Qs.b` retira el registro, ejecuta `bcI` y emite el evento de área 10011. `faZ.baE` retira además otras áreas en la misma XYZ cuyo propietario sea el mismo objeto. Son caminos distintos: `Qs.b` no llama por sí mismo a `faZ.baE`; el helper local retira exclusivamente el registro solicitado, pero no inventa un productor de paquetes o eventos para una operación de retirada que todavía no esté integrada.

La finalización del lanzamiento íntegro de Esfera 5345 y su presentación en el cliente requieren una prueba por la entrada común. El codec aislado no demuestra funcionamiento visual ni cobertura completa de todas las áreas.


## Enrutamiento común de grupos y regresión Ready

El probe real `ProbeNativeGroupCellRouting` cubre 64 casos de `eYg` y siete subclases: menos de tres parámetros selecciona actores; con tres o más, `So(2)==1` selecciona actores y `So(2)==0` selecciona celda. Cualquier otro valor hace ambas propiedades falsas. No es un enum inválido: el estado ligado al carrier usa la ruta `Qe.d`, distinta de la selección fresca de `Qe.a`. El efecto suscrito 327548 (999, valor10) reveló esa distinción.

La reparación fue comprobada con `.runtime/local/ready54-routing-fixed.json`: 54/54 inicializaciones Ready, todos los originales preservados y hashes de fuentes estables. Esta prueba acredita inicialización transaccional, no juego completo ni retirada visual.

## Consultas de casilla y equipo

El parser `eQd` asocia token25 `CellContainsSpecificEffectArea` a `eIE` y token166 `GetTeamEffectAreaCountInRange` a `eLw`. Bytecode completo preservado en `.runtime/local/native-area-new-queries.txt`.

`eIE.a` selecciona la casilla objetivo mediante `eII.d(true,...)`, exige contexto `fbX`/`eVw`, filtra `Qq.bct()` por referencia de prototipo y opcionalmente identidad del propietario `PV`. La contención llama `Qq.d`; el contrato de hora representado usa XY, no Z. `eLw.d` utiliza equipo `Qq.bcM()==caster.bcM()` y filtra **tipo** `Qq.aeV()`, no referencia. El centro es caster salvo selector literal `target`; excluye la propia área si el caster es Qq. Distancia `ala.c` y máximo negativo conservan la regla ya auditada: máximo negativo omite ambos límites.

Implementación limitada explícitamente a registros propios `faZ/anD` acreditados, separados del roster de actores. Un área de otro contrato o propietario sin snapshot no se interpreta como vacía: produce rechazo. Las consultas no conceden soporte de creación, expiración o eliminación a familias de áreas todavía no implementadas.

## Propiedad retenida de 315

`eYQ.bbR()` retira su área `oAP` de `PN.baf()` sólo si existe, `rGS` (keep) es falso y `Ty()` acredita ejecución. Después llama al cleanup de `eZR`. `ProbeNativeAreaRemoval` ejecutó este método real en las cuatro combinaciones de keep/ejecución; un `Qs.b` instrumentado contó exactamente una llamada sólo con keep=false/ejecutado=true. La instrumentación no simula eventos o gráficos.

La implementación conserva un ledger separado `native_owned_area_effects`: UID del runner, UID del área, caster que posee el Qf, parent estado, payload original y flag keep. El registro central usa ese ledger para sincronización y retirada por propiedad. El paquete 13560 conserva bytes completos del runner creado, sin añadir target ficticio. La retirada del runner mantiene el área con keep=true y retira exclusivamente su área con keep=false; no activa la limpieza separada `faZ.baE`. Sigue restringido a las 13 definiciones nativas de hora `faZ/anD` sin efectos/máscaras/callbacks. No acredita otras clases de glifos/trampas, suscripción de creación, callbacks ni juego visual.
