# Solución — 27

## Clima actual 13948

El servidor persiste el estado compartido por mapa, instancia y región. `territory_cells.py` resuelve la región desde la celda nativa; `territory_weather.py` conserva el payload de13948 y solo reemplaza el enum al aplicar una transición local configurada. El bootstrap publica el estado actual, y el tick/retry usa outbox. La flora consulta el clima persistido sin atribuir efectos a floats no interpretados.

La cobertura local activa inicializa las274 regiones con `ABSENT` y valores neutrales configurables; el snapshot anterior se mantiene en su propio ámbito. Es una política de Wakemu, no una importación meteorológica oficial.

## Forecast 13895 en fuente

El parser del cliente confirma un envelope y registros nombrados, implementados en `territory_weather_forecast.py`. La política local queda versionada por `(map_id,instance_id,region_id)`, con hijos estructurados y outbox atómico. El upsert solo permite subir versión; la lectura fija la fila de autoridad mientras recupera registros; los eventos atrasados se superseden. El publicador comprueba la lease/generación y vuelve a validar mapa, instancia y región antes de enviar. Los errores conservan el evento pendiente.

El tick climático de fuente también drena el outbox de forecast. `send_planting_context()` envía12789 con el snapshot ecológico durable, luego13948 y13895. `packet_for_territory()` toma la configuración exacta de la instancia e incluye un paquete vacío cuando no hay forecast para limpiar estado previo. El smoke TLS completo pasó en una candidata aislada; falta aceptación visual y despliegue de058.

## Límites y recuperación

No se encontró productor de forecast oficial ni datos de calendario para los territorios. Los campos se mantienen en su dominio de wire y sus unidades físicas quedan sin afirmar. No clonar el clima de otra región ni inventar conversiones. Migración058 y ruta de forecast son fuente no desplegada; 056 es el baseline local desplegado según el estado de runtime comunicado por root.

Antes de desplegar058, aplicar migraciones a una base de prueba aislada, ejecutar gate y socket smoke, y conservar backup y hash del contenedor base para mantener intacta la IA y los módulos de combate.
