# 4. El porcentaje de plantación mostrado no es real

Hacer que la probabilidad autoritativa y la disponible para presentación describan la misma regla, sin tocar el cliente.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Closed by Hector on2026-10-11 with an accepted final limitation.** The ordinary existing profile keeps its fixed visual1%. This does not mean the actual server planting roll is1%. Optional native percentage work remains inactive and historical; native activation and general extra-effect integration are not requirements for this issue. No client files or flags were changed.

The implementation and investigation sections below preserve their dated evidence and do not override this closure.

## Dependencias

1, 6, 27, 28. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Permiso no equivale a probabilidad; repetir una solicitud no vuelve a sortear el resultado.

## Cotejo actual y resultado fallido

Historical review: `dev.am` calcula `round(100*p)` para la celda, mediante `fyi.b` con terreno, clima y modificador de oficio. El parche `OpenPlantingAgent` sustituye precisamente esa función por1: explica el1% visual sin acreditar una tirada del servidor. El servidor cargado todavía finaliza siempre con éxito. No se cambia el cliente como parte de esta solución.

En fuente, migración018 y `planting.complete(success=False)` permiten persistir un fracaso: consume una semilla, guarda el resultado sin recurso/grupo, publica12954 falso y delta12470; no concede XP ni crea población. El retry usa el recibo y no vuelve a consumir. Gate de fallos/recibos y recursos:112 pruebas OK en PostgreSQL aislado; sin despliegue ni RNG integrado. La fórmula nativa y los carriers del contexto siguen bajo cotejo para alinear presentación y autoridad.

La fórmula y el redondeo están implementados en `planting_probability`, con pruebas de casos nativos en curso. No se añaden escalones por nivel: el cotejo nativo no usa el nivel directamente. Se preservan los requisitos mínimos de oficio y los modificadores de probabilidad como conceptos diferentes.

## Tirada transaccional implementada

`planting.complete(probability=...)` ahora compara una muestra uniforme de53 bits con la probabilidad sin redondear, dentro de la transacción y después del recibo y la validación de semilla/celda. El recibo guarda probabilidad y resultado; repetir la operación reutiliza ambos, incluso si el caller cambia la probabilidad. Un bloqueo asesor por mapa/instancia/celda y una nueva comprobación impiden cobrar una semilla por una casilla ocupada después de iniciar.

La migración018, todavía no aplicada al servidor, se amplió con esa evidencia persistida. Gate ampliado en ejecución. El runtime aún debe aportar contexto autoritativo; no se afirma que las solicitudes del juego estén usando ya RNG.

## Contexto de superficie y recurso

Se exportaron533 clases climáticas nativas y se empaquetó `resource-climates.json`. `planting_probability.for_cell` resuelve la superficie exacta por XYZ, obtiene ground y territorio, aplica precedencia de recurso incluso cuando su umbral es0 y resuelve compatibilidad por clase climática. Rechaza alturas ambiguas, contexto/clima desconocido y entradas sin metadatos. Clima territorial y bonus efectivo siguen siendo entradas autoritativas obligatorias, no se infieren del recurso ni del nivel. Pruebas ampliadas en curso.

Gate anterior de recibos/RNG/celdas: **117 pruebas OK** en PostgreSQL aislado; no se afirma integración del runtime ni despliegue018.

## Conexión de la ocupación con la tirada

La fuente de `Plantings` admite ahora un resolver autoritativo de probabilidad. Al iniciar valida y congela la probabilidad en el ticket antes de reservar la ocupación; al terminar la entrega a la transacción. El paquete del cliente no decide ni el porcentaje ni la tirada. Las regresiones de esta conexión están en ejecución. El servidor aún no configura ese resolver: falta conectar clima territorial y bonus efectivo; no está desplegado este cambio ni la migración018.

El gate de cálculo/contexto (`test_planting_probability test_planting_context`) pasó **16 pruebas**, incluyendo catálogo completo de533 recursos, incompatibilidad climática, precedencia de umbral0 y rechazo de superficies ambiguas.

## Política de duración en PostgreSQL

La migración019 define `planting_duration_ms=3000` como política local. Cada ocupación lee y valida un entero entre1 y300000ms antes de reservar y congela el valor para el timer nativo y el control de finalización. Cambiar la política afecta las ocupaciones nuevas. Se eliminó el default del constructor; no se mantiene un segundo origen de configuración. Migración sin desplegar, regresiones de duración en ejecución. La conexión anterior de probabilidad pasó39 pruebas PostgreSQL aisladas antes de este cambio.

## Autoridad territorial de clima

Gate de duración actualizado: **41 pruebas OK** con019 en esquemas privados. La revisión del replay confirmó que13948 se reenvía desde capturas mientras12789 se sintetiza por territorio; no existe todavía una autoridad climática propia. La migración020 introduce estado por mapa/instancia/territorio, conserva los37 bytes nativos para publicación y no rellena territorios desconocidos con ABSENT. El lector resuelve la celda nativa exacta y rechaza contexto ausente. Pruebas en ejecución. Falta verificar correspondencia entre payload/enum y origen de los datos antes de implementar el escritor y conectar el runtime.020 tampoco está desplegada.

## Despliegue verificado — 6 de octubre

Imagen `31e34eb30a8278df34d0216abc8d8ce2a5cfcf2433f45510d0c49601f637b22c` cargada tras respaldo privado y comprobación de cero combates/recolecciones activos. Migraciones018–020 aplicadas; SQL confirma duración3000ms, columna de probabilidad y climaLIGHT únicamente en mapa1134/instancia0/territorio79301. Docker healthy y `/health` consultado dentro del contenedor devuelve `ok:true`, almacenamientoPostgreSQL. El intento por el puerto publicado desde el host devolvió respuesta vacía; no se atribuye esa comprobación al endpoint interno exitoso.

El enum Vl del JAR coincidente con la captura acredita ABSENT0/LIGHT1/HEAVY2/STORM3. El escritor valida el payload37/enum/floats y territorio nativo, incrementa revisión; el lector rechaza discrepancias y alturas ambiguas. El dispatcher publica estado territorial después de12789 y omite clima capturado en replay. Gate amplio:152 pruebas OK. Resolver integrado con proveedor obligatorio de bonus:57 pruebas OK. **El dispatcher todavía no configura ese proveedor ni activa el cálculo probabilístico para solicitudes reales; issue4 sigue En revision.** No hubo cambios de reglas de combate ni hechizos.

## Perfiles de probabilidad y bonus efectivo

El actor nativo eRN devuelve0 al faltar PLANTATION_PROBABILTY; el servidor serializa PERSONAL_EFFECTS con tres contadores cero y RUNNING_EFFECTS ausente. Equipo y aptitudes exportados no contienen stat2000; el generic2000 del Anillo es otro identificador. El proveedor base0 valida que se mantenga ese snapshot vacío y exige otro proveedor si cambia. No deriva bonus del nivel de oficio.

El territorio79301 tiene9593 superficies con ground0, sin definición en planting-grounds. El perfil abierto permite esas superficies intencionadamente; forzar un terreno nativo inexistente sería incorrecto. DB021 establece la política local abierta0.01, coincidente con el indicador1% del OpenPlantingAgent instalado. Ese perfil usa la política SQL y la tirada transaccional; el perfil nativo conserva terreno/clima/bonus y rechaza contexto desconocido. Ambas rutas están conectadas en fuente. Esto no convierte el perfil abierto en una fórmula oficial: modificar su porcentaje en SQL no modifica el indicador hardcodeado del cliente. Pruebas en curso;021/dispatcher nuevo todavía no desplegados.

## Estado vigente: Cambio hecho no confirmado

Imagen `ffd6979a8006e4adc88d13f6e713613be8b56bfeb9066c68714b3f8c10afb888` desplegada con021 tras respaldo privado y cero combates/recolecciones activos. SQL confirma política abierta0.01 y duración3000ms; health interno confirma PostgreSQL operativo. Gate actualizado72 pruebas OK. La instancia real configura el resolver, y el log planting_completed incluye probabilidad/resultado. Falta aceptación en partida: solicitada a Luna en personaje de auditoría propio. Las notas anteriores «sin desplegar/no conectado» son historial, sustituidas por esta evidencia. No se da por completado el issue.

## Conectividad y aceptación pendiente

Se corrigió el bind interno de Compose a0.0.0.0; los tres puertos publicados permanecen127.0.0.1 en el host. Antes el health interno era correcto pero el puerto publicado devolvía respuesta vacía. Ahora `curl http://127.0.0.1:18081/health` desde el host acredita `ok:true/storage:postgresql`. Se renovó únicamente la sesión privada de la cuenta de auditoría5 y Luna reintenta la aceptación. Este ajuste no cambia codecs ni reglas de combate.

## Prueba nativa de fallo — 6 de octubre

Con un personaje nuevo de auditoría, la interfaz mostró1% y el servidor completó la ocupación nativa de tres segundos. El cliente anunció pérdida de una semilla; PostgreSQL acreditó cantidad5→4, recibo `success=false`, `probability=0.01`, recurso y grupo nulos. No apareció recurso/outbox de crecimiento ni crédito de XP. Captura de protocolo:13220→12815→13429→12954→12470. La prueba confirma el resultado y consumo de este intento; no constituye una estimación estadística del1%. La ruta de éxito todavía requiere aceptación visual. Evidencia privada conservada en `.runtime/local/instances/audit-profession-013/`.

Ruta de éxito nativa comprobada con override temporal de probabilidadSQL1, restaurado a0.01 antes de completar la ocupación: semilla4→3, recurso60 en la celda elegida y +10XP de Herbolario, con un solo recibo XP. El recurso avanzó a etapa4; reentrada para cotejar cantidad/UID todavía en curso. El override comprueba el camino de éxito, no acredita éxito estadístico a1%.
