# 31. Configuración repetida de celdas durante colocación

Variar formaciones legales por encuentro sin incoherencia entre jugadores o reconnect.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Auditoría y propuesta de cambios del **servidor**. Se inició la implementación en fuente; no está desplegada. El cotejo distingue lo existente de lo pendiente; ninguna prueba de base certifica automáticamente el recorrido completo.

## Dependencias

0, 14, 18, 29. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Layout elegido una vez por encuentro, legal para todos y persistente a través de sesiones.


## Variación determinista en fuente

El generador admite una semilla de encuentro que cambia el desempate entre celdas a igual distancia nativa. Conserva semillas de actores, alturas, aristas dirigidas y prioridad de proximidad. El modo anterior sigue siendo el default hasta integrar la política SQL y la identidad durable del combate. `PYTHONPATH=server:server/tests python3 -m unittest test_combat_placement_cells`:6/6 aprobadas; prueba20 identidades con variedad real, capacidad, disjunción y reintento estable aunque cambie el orden de entrada. Pendiente parametrizar capacidad/versión en DB, persistir la selección y conectar el caller; no acredita variedad en el servidor activo.


## Política y persistencia implementadas en fuente

Migración061: `fight_placement_policy` (versión1,12 plazas por equipo, variación habilitada), capacidad1–127 y selección guardada en `fight_placement_layouts`. El handler13130 congela el layout tras asignar identidad durable y antes de serializar colocación. Reintentar devuelve el mismo layout aunque cambie la política; nueva pelea usa la política vigente. Se preserva la identidad nativa de arena separada del scope mapa/instancia. Lease obsoleta rechazada incluso si ya existe layout. Gate Docker/PostgreSQL `test_combat_placement_policy test_combat_placement_cells test_combat_arena_selection`:15/15 OK; incluye SQL inválido sin layout parcial, reconexión/reapertura y cambio de capacidad12→2 solo para pelea nueva. No desplegado: falta candidata congelada y TLS de entrada/retorno compartido antes de recargar.

El helper admite una transacción prestada para preparar duelos sin abrir otra conexión ni bloquear la propia fila sin commit. Regresión adicional: fallo de serialización revierte el layout junto a la preparación; gate actualizado15/15.


## Candidata congelada y TLS individual

Imagen `83e400a3f4ecb398427bb27085545952c8d60d95431db0b1a706682a9f5226b5`, basada en live e839. Overlay aislado: generador, política, hunk13130 y migraciones060/061 (060 requerida por secuencia; no contiene handlers de duelo nuevos). Gate congelado48/48 de colocación, arena, Registry compartido y lifecycle. El primer intento de gate falló por rutas de fixtures y nombre de módulo inexistente; se corrigió montaje y se repitió completo. TLS individual de combate/return/overflow/reconnect/recycle/discard aprobado en DB `wakemu_candidate_placement_061_20261007`; SQL acredita un layout persistido con12+12 y pelea finished. El harness privado exige exactamente esa DB; no debilita la prohibición de usar runtime. TLS compartido iniciado, aún sin resultado. No desplegado.

TLS compartido aprobado dos veces en la imagen83e400: ambos propietarios nivel1→8,14365XP/5kamas cada uno, report push sin peticiones de juego del segundo cliente, replay y retorno de ambos. Cambio de política SQL solo en DB desechable a versión2/capacidad4: nueva pelea persisted4+4 y finished; peleas anteriores conservan versión1/12+12. No se tocó runtime.

Regresión de preparación concurrente añadida: cuatro llamadas en dos hilos confirman una sola fila y layouts iguales. Gate congelado actualizado49/49; no se cambió la imagen ni runtime.

Prueba adicional de variedad con exportaciones reales de mapas1134 y527: diez identidades por misma arena nativa, semillas conservadas y flags wire coincidentes con plazas. Módulo de colocación7/7 aprobado; no se exige variar geometrías donde no exista una alternativa legal.

Verificación posterior de la imagen83e400: 26/26 pruebas de política, celdas, arena y lifecycle aprobadas, incluida variedad sobre mapas nativos1134/527. Un gate ampliado con las pruebas actuales de combate compartido obtuvo49/51: dos verificaciones AST exigen handlers de duelo añadidos después de congelar esta candidata y ausentes por diseño de este overlay. No acredita el gate integrado de duelos; este se valida en su candidata propia. No se modificó el servidor activo.
