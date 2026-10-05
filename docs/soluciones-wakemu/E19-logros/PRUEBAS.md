# Pruebas y criterios de cierre

## Ejecutado en esta revisión

- Extracción con lectores actuales `apw/aJM/aJU/aJR`:3278 definiciones,6029 objetivos,5593 recompensas,396 variables,481 categorías,297 listeners. Lectura local, sin ejecutar el juego ni Dofus.
- Resolución de IDs/textos de la captura y premio 4228→16942×1.
- `oN.aG` + `bdM.dT`: sección vacía actual 21B,blob 18B, sin bytes sobrantes.
- Snapshot sintético variable 695=49; sustitución absoluta mediante `bdM.o` por 50 y cuerpo `cty`13295 leído. No se afirma dispatch en una sesión real.
- Snapshot sintético 35B:4228 activo/completo,8716 completo y 4228 seguido, restaurados por consumidor nativo. La combinación es una fixture de campos, no una secuencia autoritativa de juego.
- Round-trip `fCV.di/fa` zlib correcto; constructores `cnI/cnJ/cnK` confirmaron opcodes y framing nativo.

Artefacto: [probe](probe-logros-catalogo-y-wire.json). Fuentes reproducibles privadas `.runtime/local/AchievementCatalogAudit.java` y `AchievementWireAudit.java`. Comandos: `javac -proc:none -classpath 'client/lib/*' ...`; `java -classpath '.runtime/local:client/lib/*' AchievementCatalogAudit`; el probe wire recibe el hex `ACHIEVEMENTS` actual. Son verificaciones del consumidor, **no tests de una implementación inexistente**.

## Matriz de aceptación para implementación

| Caso | Comprobación requerida |
| --- | --- |
| Login nuevo / reconexión | Objetivos y contadores correctos; ningún grant al abrir diario o reconectar |
| Contador límite |49→50 activa solo regla/listener correcto; valor absoluto repetido no suma |
| Evento duplicado | MismoUUID recibido 10 veces produce un avance y un grant |
| Objetivos independientes | Cinco de seis objetivos 4228 no completan padre; el sexto concede exactamente una 16942 |
| Entrenamiento 3976 | Cinco finalizaciones reales diferentes;4 no bastan; derrota/replay no cuentan; título 520 y 14168×10 una vez |
| Cadena de padres | Orden diferente de hijos produce mismo estado; eventos tardíos y reinicio no duplican cascada |
| Inventario lleno | Premio no perdido ni duplicado; entrega pendiente/rollback visible y durable |
| RecompensaXP/kamas | Igualdad DB/journal/paquete/diario; subida de nivel atómica sin curar indebidamente |
| Dos clientes/personajes | Progreso separado y permisos por sesión; compartir no concede ni copia finalización arbitrariamente |
| Seguimiento |13175 persiste selección y límite;13371 y bootstrap coinciden; completar retira seguimiento |
| Activación |13397 rechaza ID inválido, nivel/prerrequisito fallido, cooldown y replay; devuelve estado coherente |
| Reset / fallo |12012/12023 limpian exactamente estado afectado; no borran recibos durables por accidente |
| Repetible / periodo | Fronteras de fecha, expiración y reinicio; mismo ciclo una entrega; ciclo nuevo según regla |
| Contenido no soportado | Criterio/handler desconocido no completa ni concede; diagnóstico identifica regla y fuente faltante |
| Caídas | Antes/después commit y antes/después envío; outbox reanudada, premios no duplicados |
| Carga | Varios combates y acciones por zona; fanout indexado y tamaño máximo blob comprobados |

Pruebas GUI pendientes con personaje nuevo y Luna low o usuario; no se han marcado como ejecutadas. Para cerrar E19 hace falta progreso, recompensa y reconexión reales de las familias habilitadas, además de catálogo de reglas pendientes explícito. No se reiniciaron servicios ni se modificaron bases.
