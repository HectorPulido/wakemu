# Registro por13497: contratos por definición, no por familia

Auditoría independiente offline, sin motor/GUI/reinicio. Tool `sniffer/java/AuditNativeObservationGuards.java`; resultado `docs/reports/combat-inventory/native-observation-guards.json`. Scope: todas las definiciones instaladas, incluidas antiguas/no alcanzables. Los conteos no representan cobertura de hechizos actuales.

## Contrato original

`aTR.cbj` registra en Qf sólo si `(Ty || bbW) && (aZN || bbW)` y existe actor/manager. El owner es caster cuando bbB o aZA, target en los otros casos. En cualquier caso llama bbE/fSn; ver un efecto ejecutado o stats actualizadas no prueba retención.

Las21familias auditadas heredan `Qe.aZN`, `eZR.Ty` y `eZR.bbW`; la clase400 no tiene un override exclusivo que explique la diferencia. `aZN` consulta si hay bits en aZH, aZG, aZJ, aZK o aZL del PK. No incluye aZI/aZO. No interpretar esas cinco máscaras como sólo objetivos: contienen filtros/eventos.

`bbW` exige PK, PL y modo aZD2; devuelve si el delay original `eVv.eo(fRR)` no es cero. No equivale a duración!=0. `Ty` considera bfM, duración/permanencia y modo de definición; necesita nivel/contexto real. Estos contratos evitan concluir que aZNfalse siempre implica descarte.

## Resultado de definiciones instaladas

|Familias|Runner|aZN true/false|Situación|
|---|---|---|---|
|20/31/41/191|eWN|0/10634;0/3473;0/2484;0/390|13497 depende de escape bbW; registro pendiente para casos actuales|
|56/57/192|eWO|0/81;0/192;0/70|Igual; no cambiar opcode sin evidencia de aplicación|
|1013|eWx|0/738|Armor HUD puede actualizarse por stat snapshot; no prueba Qf retenido|
|986|eZI|0/63|Registro pendiente|
|193|eWQ|0/316|Registro pendiente|
|1201/1202|eWS/eWT|0/3;0/2|Registro pendiente|
|402/649/1065|eXG/eWn/eZe|0/453;0/267;0/1|Registro pendiente|
|877|eWV|1/178|Depende de PK; no familyconstant|
|330|eYg|8072/18325|408737 con PL1 probado13497→Qf1/UI1; resto depende PK/timing|
|341|eXR|8/217|PK/timing pendientes|
|352|eYA|0/17|Riesgo si13497 y bbWfalse; no prueba todosmal|
|1103|eYB|20/0|aZNtrue actualinstalled; falta Ty/owner/context por caso|
|400|eXE|14/11328|150327 probado13497→Qf0;12613false→Qf1/UI1; oficiales40012613|

No convertir conteos a política global de opcode. El probe `ProbeNativeStateChildDelivery` y las capturas oficiales acreditan400 y el grupo330408737; los demás necesitan decode+Qf de payloads reales y contraste de opcode oficial, conservando PL/timing/UID/status. `owned_effect_application` proporciona layout13497 pero no establece el contrato de registro de cada caller. La nueva selección400 está limitada al contrato demostrado.

## Reproducción

```sh
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/ProbeNativeRegistrationGuards.java sniffer/java/AuditNativeObservationGuards.java
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java -cp '.runtime/local/classes:client/lib/*' ProbeNativeRegistrationGuards
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java -cp '.runtime/local/classes:client/lib/*' AuditNativeObservationGuards .runtime/local/native-observation-guards.json
```

Ambos ejecutados correctamente. El segundo lee bdata local y crea runners/PK originales, sin actores, mutaciones de gameplay ni cliente gráfico. Por diseño no evalúa Ty/bbW sin autoridad de ejecución real.

## Dos controles con payload oficial sin modificar

`ProbeOfficialStatDelivery.java` ejecutado con los iN extraídos por root de capturas oficiales (archivo privado `.runtime/local/official-stat-effect-delivery-samples.json`).193 y649 preservan todos los bytes del protobuf: UID/baseUID/PK/PL/valor/timing/context/AdditionalDatas. Se resuelve PK original porbcA y PL original porfyW;649 usa actorPC bjo con bPN/fyR/bPS reales para decodificar AdditionalDatas, sin inventar parámetros de grant.

|Muestra|Ty/aZN/bbW|13497Qf|12613falseQf|
|---|---|---|---|
|193,PK326451,PL1/467206145|false/false/false|0|0|
|649,PK326447,PL1/467206145|true/false/false|0|1|

PASS con asserts de guard/registro y cola original.649 queda bbs=false por12613false.193 demuestra que aparecer por12613 oficial no implica ser un efecto retenido: ninguna ruta fuerza registro cuando Tyfalse. Este resultado respalda una política acotada por guards y autoridad de retención, no una conversión global por familia. Salida privada `.runtime/local/official-stat-delivery-probe.txt`.

```sh
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/javac -proc:none -cp '.runtime/local/classes:client/lib/*' -d .runtime/local/classes sniffer/java/ProbeOfficialStatDelivery.java
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java -cp '.runtime/local/classes:client/lib/*' ProbeOfficialStatDelivery .runtime/local/official-delivery-193.bin .runtime/local/official-delivery-649.bin
```

Las clases de apoyo ProbeNativeStateManager/ProbeNativeStateChildDelivery se compilan con el comando de native-state-display-metadata.md.

## Autoridad compacta de owner

`server/protocol/native-runner-registration-owners.json` contiene318entries del registry, con287pares literales bbA/bbB acreditados por ASM. Sólo métodos que consisten exactamente en ICONST0/1+IRETURN producen booleanos; cualquier lectura de campos, rama o llamada devuelve null y requiere contexto real. No se extrapola el valor por defecto del prototype a un runner dinámico.

Exportador reproducible `ExportNativeRunnerOwners.java`, con add-exports ASM. Generado dos veces, cmp idéntico. Tres pruebas focused PASS. eWW/eWN/eWO/eZI/eWS/eWT/eWn/eXE y armor1013 usan (bbAtrue,bbBfalse);402 y352 usan(false,true).330/341/1103 son dinámicos y quedan null. Esto no contiene aZA, que depende del PK.

Atención al owner: aTR usa `aZA || bbB` para elegir caster; aVo false usa `aZA || (bbB && !bbA)`. Una política de entrega debe verificar equivalencia de owner cuando cambie de ruta. aVo false sólo registra siTy, no por el escape bbW. Efectos delayed conTyfalse perobbWtrue deben conservar el recorrido acreditado13497. La autoridad de retención no puede reemplazar estos guards ni activar ejecución cliente.
