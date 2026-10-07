# Pendientes — 27. Clima por territorio

| Pendiente | Estado y cierre requerido |
| --- | --- |
| Forecast oficial para todos los territorios | Sin productor/catálogo oficial disponible. La fuente admite políticas locales explícitas; sus valores no representan clima oficial. |
| Aceptación visual del panel | El smoke TLS en candidata cubre bootstrap, regiones, clear, outbox y reconexión; falta confirmar visualmente el panel meteorológico. |
| Configurar una previsión local de prueba | La política está versionada y durable, pero aún no hay una configuración de prueba publicada en el servidor. |
| Aceptación visual | Verificar el panel meteorológico y la limpieza al entrar en un ámbito sin forecast después de uno configurado. |
| Unidades y fórmulas de muestras/clima | El parser consume las unidades nativas de byte; no se comprobó conversión a grados ni efecto de los seis floats en crecimiento. Mantenerlas nombradas y sin efectos no probados. |

No inferir temporadas, clima o efectos de flora desde otra región ni desde el orden de los campos. El gate de código no sustituye la integración del dispatcher ni la aceptación visual.
