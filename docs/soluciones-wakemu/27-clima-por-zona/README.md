# 27. Clima por territorio

> Closed by Hector on2026-10-11: "Clima ok". The deployed regional weather/forecast implementation and109-test native verification are accepted. Earlier pending-acceptance wording below is historical.

> Current release2026-10-11: complete shared World/AI/ecology/admin deployed and automatically verified. Migration123; stable window released08:07 UTC. [Deployment evidence](../../reports/SYSTEMS-DEPLOYMENT-20261011.md). Graphical acceptance remains pending; any earlier prepared/not-deployed wording below is historical. Native planting bonus stays disabled pending its separate native-display acceptance.


El servidor mantiene clima compartido por territorio, conserva el estado al reconectar y aplica transiciones explícitas desde PostgreSQL. La cobertura general activa usa la política local `ABSENT`; no copia el único snapshot nativo a otras regiones ni se presenta como clima upstream.

## Estado actual

Root informó que la imagen `6319c87d` está activa sobre la base que conserva la IA. La migración056 inicializa las274 regiones nativas con política local y materializa el estado por instancia sin modificar filas preexistentes. El cron climático publica las transiciones de13948 cada5s; las pruebas TLS previas verificaron scoping por región/instancia y reconexión. La aceptación visual del panel meteorológico sigue pendiente.

El parser nativo de forecast13895 está cotejado con el cliente instalado. La fuente añade un codec estructurado, política local versionada por mapa/instancia/región, outbox durable y conexión de13895 al bootstrap y al tick. El bootstrap publica primero el snapshot ecológico, luego13948 y finalmente13895. No existe evidencia de un productor oficial de forecast ni de unidades físicas para sus campos. La migración058 y esa conexión son cambios de fuente y aún no están desplegados.

## Validación de la fuente de forecast

La prueba Java `ForecastNativeProbe` decodificó correctamente un vector nombrado con el parser `bRV.fe` instalado. El encoder cubre el envelope, registros de12bytes, enum meteorológico, ajustes estacionales y el padding estructural. El vector es de política local; no es una captura nativa.

El outbox usa versión creciente y clave exacta `(map_id, instance_id, region_id, policy_version)`. Una nueva versión supersede las anteriores sin perder el evento vigente. Publicar revalida la sesión actual y solo envía13895 a personajes del mapa, instancia y región destinatarios. Si el envío falla, la fila permanece pendiente para reintento. El bootstrap devuelve un paquete vacío explícito cuando esa instancia no tiene forecast y así puede limpiar un forecast anterior del cliente.

Gate Docker con PostgreSQL aislado y las59 migraciones presentes al correrlo: **76/76 pasaron** entre codec, política/outbox, clima existente, bootstrap ecológico/meteorológico, transiciones, movimiento, flora, scheduler y migraciones. El smoke TLS estricto pasó en `wakemu-sublimation-weather-level-candidate:20261007-final2` (digest `e839fd35…`), con 12789, 13948 y13895 en dos regiones e instancia no-cero; verificó clear vacío, update regional por outbox, reconexión y probabilidad de plantación. La migración058 no está desplegada; la aceptación visual sigue pendiente.

## Prueba manual general

Con un personaje de prueba en el mapa1134, ejecutar `!pos`, después `!tp 1134 -39 -72 47` (territorio79301) y `!pos`. Abrir **Panel meteorológico** y anotar estado y valores. Ejecutar `!tp 1134 -23 -143 70` (territorio79201), confirmar el estado de esa región, volver a79301 y comprobar que conserva su estado. Salir y volver a entrar en ambos territorios para verificar el bootstrap actual. Las coordenadas son posiciones transitables del mapa.

La ruta de fuente envía el payload configurado o un paquete vacío de limpieza al bootstrap; el tick publica cambios pendientes. El smoke usa valores de política local y no valida fórmulas meteorológicas oficiales, que no están disponibles.

## Referencias

[Cotejo nativo y límites](COTEJO.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md) · [Revisión y decisiones](REVISION-RESPUESTAS.md)


### Despliegue integrado verificado

Imagen `e839fd35a2c123b8c83006528cfabc8f7bb5c8e5c3d0973f347ffcadc5321742` desplegada en world; Docker healthy y `/health` PostgreSQL correcto. Migraciones057–059 aplicadas;388 patrones de sublimación en SQL. Gate de la imagen198/198 aprobado y TLS de combate individual/compartido, sublimaciones y clima acreditados. Respaldo previo privado `.runtime/backups/pre-integrated-20261007.dump`, archivo CUSTOM con793 entradas TOC. Aceptación visual pendiente; no implica cierre completo del issue.

## Regional simulation follow-up — 11 October

Source now includes migration118 and a configurable deterministic regional
weather model, with coherent five-day forecasts, seasons, instance-scoped
publication, atomic state/forecast updates, restart catch-up and first-entry
bootstrap. Operator snapshots, explicit transitions and separately configured
forecasts retain precedence. These are documented emulator rules; no official
weather probabilities or unverified physical calibration are claimed. Native
consumer review maps all 13948 temperature/wind fields, and the automatic encoder
now derives them from the same model as the forecast. Seasonal forecast clamp
bounds match the modeled range. Explicit operator snapshots are preserved.

Luna's combined planting/weather gate passed 109/109 without skips, and the
installed native weather consumer oracle passed. Source is READY as of
2026-10-11 07:20:14 UTC. Complete world/ecology deployment and graphical
weather-panel acceptance remain pending. See the
[implementation and complete acceptance](../../reports/REGIONAL-WEATHER-20261011.md).
Historical statements above describe earlier versions.
