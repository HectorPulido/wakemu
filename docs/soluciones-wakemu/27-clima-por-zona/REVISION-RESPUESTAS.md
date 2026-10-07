# Revisión técnica — 27

## Estado 7 de octubre de 2026

### ¿Qué está desplegado?

Root informó que `6319c87d` está activo sobre la base con IA conservada y que la política local056 ya se aplicó. La cobertura usa `ABSENT` configurable y no copia estado meteorológico entre territorios. El cron de transiciones13948 está activo cada5s. El panel requiere aceptación visual.

### ¿Se conoce el protocolo de forecast?

Sí, su layout estructurado y enums están cotejados con el cliente instalado y el vector local pasó `ForecastNativeProbe`. Esto verifica parser y serialización, no la procedencia de los datos. No se localizó productor oficial ni unidades físicas de las muestras.

### ¿Qué aporta la migración058?

Política de forecast con filas diarias y estacionales, particionadas por mapa, instancia y región, más outbox por versión. Los guardados son monotónicos aunque compitan primeras escrituras. El lector mantiene una versión coherente mientras recupera las filas. Publicación usa la sesión actual y filtra por región exacta; los fallos quedan reintentables y las versiones anteriores se coalescen. La respuesta vacía de `packet_for_territory` sirve para limpiar una previsión anterior en el cliente.

### ¿Qué falta?

La migración058 y sus helpers siguen en fuente, no desplegados. `send_planting_context` envía el snapshot ecológico,13948 y13895 en ese orden, y el tick drena el outbox. El smoke TLS estricto pasó contra la candidata final2 sobre DB aislada: verificó 12789,13948 y13895, clear, outbox regional, reconexión y contexto de plantación. Falta la aceptación visual del panel. No hay datos oficiales para poblar un calendario real; una previsión configurada por operadores debe rotularse como política local.

### Gate actual

Gate Docker PostgreSQL aislado con las59 migraciones presentes al correrlo: **76/76 OK**. Incluye suites weather existentes, política/outbox forecast, publicación de snapshot ecológico/meteorológico, movimiento, flora, tareas globales y migraciones. El probe Java del JAR del cliente confirmó el vector sintético con el parser `bRV.fe`. El smoke TLS completo confirma el flujo de fuente en candidata, pero no despliegue de058 ni aceptación visual.
