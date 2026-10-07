# 2. Un bebé tofu nunca crece

Transformar un monstruo joven en su etapa adulta según una política documentada por familia.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Solucionado totalmente.** El usuario confirma crecimiento de los Tofus hasta etapas posteriores poderosas. La maduración funcional queda aceptada; el ritmo y la fuerza final corresponden a balance separado.

Los apartados siguientes conservan la investigación y los gates anteriores; esta aceptación sustituye sus estados históricos pendientes.


**Cambio hecho no confirmado.** Ritmo corregido y desplegado mediante035/imagen366629bb, Docker healthy. Gate específico92 y final397 OK; falta aceptación visual del ritmo.

### Ritmo de maduración — 2026-10-06

Usuario identifica los Miaumiaus cerca de mapa527/(27,3,0). El catálogo siembra referencia2616, nivel4, región66701. Familia563:2616/2617 →2598 →1816. La base actual confirma transformaciones tras5–15 intentos para varios miembros, con política60s/.25/.5: mínimo2 minutos activos y media12 hasta la última etapa. No se detectó salto de etapas en esos recibos.

Migración035 preparada: intervalo general de15 minutos activos, mismas probabilidades y pausa por ausencia/combate/recolección. Reinicia también los temporizadores existentes y pendientes a un intervalo completo; conserva formas ya alcanzadas, identidades y recibos. Para esa familia: mínimo30 minutos activos y media3 horas. Pendientes pruebas automatizadas y despliegue; no cambia hechizos ni ejecución de combate.

## Dependencias

3, 20 y almacenamiento adicional. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Madurar no añade población; un miembro solo atraviesa transiciones legales de su familia.

## Revisión de catálogo y política solicitada

[Familia 68, ausencia de is_boss, ruta de respawn y límites del crecimiento](REVISION-RESPUESTAS.md).

## Implementación en revisión — 6 de octubre

Se creó `server/tools/export_monster_growth_catalog.py` y su salida `server/protocol/monster-growth-catalog.json`:108 familias plantables,105 con referencias y104 con varios niveles mínimos. Familias394/469/470 carecen de monstruos exportados;532 es terminal. Se conservan referencias empatadas como alternativas y hashes de ambas fuentes. Los rangos siguen la política solicitada por nivel mínimo; no representan una cadena oficial de edad. No se desplegó un motor de maduración.

Familia68: nivel4 refs2/39 →8 ref1 →10 ref41 →14 ref3 →18 ref4085 →23 refs44/4086. Familia81:4 ref6 →8 ref4 →10 ref5 →14 ref704 →18 ref4092 →23 refs1259/4101. `monsters.json` no contiene is_boss; el boolean crW no está acreditado como jefe y no se interpreta por nombre. La revisión posterior del constructor resolvió la clasificación, detallada abajo.

La política propuesta es evaluación cada60 segundos activos, probabilidad base0.25 con factor0.5 por rango y chance de jefe0.00001, todo en PostgreSQL. Estos defaults son balance local propuesto; aún no se aplican ni se presentan como fórmula oficial. El motor deberá conservar población/identidades, excluir combate y recolección, y pausar sin jugadores sin ejecutar tiradas acumuladas al regresar. Hechizos y reglas de combate permanecen fuera de los cambios.

## Clasificación nativa de jefes resuelta

La cadena `bbo.a(aMb,short)` pasa csc como argumento9 y csb como10 a blj. El constructor blj los intercambia al invocar eGC:10→parámetro6→pIc (ffe, combate);9→parámetro7→pIb (eHQ, mundo). Por tanto **csc corresponde a propiedades del mundo**, no a las de combate. Dos inspecciones independientes confirmaron este intercambio.

El catálogo generado clasifica por flags csc: BOSS43, ARCH45, ULTIMATE_BOSS49 y RAID_BOSS99. De720 referencias plantables,110 son BOSS en99 familias; no hay ULTIMATE/RAID en este subconjunto. Ref44 (Jalató Real) y1259 (Tofu Real) son BOSS;4086/4101 son ARCH. No se interpreta crW ni se clasifica por nombre. La cautela previa sobre clasificación desconocida queda sustituida por esta prueba. No se modificó el encoder de monstruos ni sus hechizos.

Gate de catálogo: `test_monster_growth_catalog`, **5 pruebas OK** en Docker. Verifica salida reproducible byte por byte, hashes de fuentes,720 referencias/108 familias, tiers68/81/532 y clasificación independiente:524 normales,110 jefes,86 archimonstruos. No acredita ejecución de maduración.

## Reloj persistente y selección en fuente

DB022 introduce la política local60s/base0.25/decay0.5/jefe0.00001 y relojes por monstruo con FK a su identidad persistida. `monster_maturation.observe` cuenta tiempo entre observaciones de presencia; una ausencia, combate o recolección borra el ancla activa sin descontar el tiempo restante. Otra generación de servidor comienza sin cobrar tiempo del reinicio. Al vencer deja un ciclo pendiente durable y no emite intentos acumulados ni vuelve a emitir el mismo ciclo. Cambios de referencia reinician el intervalo conservando el contador de ciclos. El caller debe observar también las zonas que dejaron de tener jugadores y mantener los locks de grupo/recolección; el daemon ya está conectado en fuente y pendiente del gate de integración.

`choose_next` usa exclusivamente el siguiente rango. Separa la chance total de jefes de la chance ordinaria decreciente; añadir referencias de jefe no multiplica la probabilidad ni convierte al jefe en una alternativa equiprobable. Un draw sin avance devuelve la forma actual. DB023 resuelve cada ciclo con recibo/outbox transaccional. El daemon publica el cambio nativo en fuente; falta verificar su integración y reconexión/partida. DB022–023 no están desplegadas. No se modifican hechizos.

Gate de reloj/selección: `test_monster_maturation`, **9 pruebas PostgreSQL aisladas OK** con022. Acredita ausencia sin consultar grupos/política, pausa por pelea/cosecha, reinicio de generación sin cobrar ausencia, intervalo congelado, ciclo pendiente durable único y fronteras jefe/ordinario/sin avance. No acredita aún cambios de forma ni scheduler conectado.

## Transformación transaccional y recuperación — 6 de octubre

DB023 añade recibos por identidad/ciclo y outbox. `attempt` bloquea el grupo y el reloj, rechaza ciclos obsoletos y monstruos ocupados antes de tirar, y confirma referencia, estadísticas nativas, revisión, recibo y siguiente intervalo en una transacción. Conserva UID, coordenadas y demás miembros; una repetición recupera el resultado sin otra tirada. Gate combinado: **18 pruebas PostgreSQL aisladas OK**, incluida carrera concurrente y rollback ante fallo inducido del outbox.

`unpublished` recupera el roster y revisión actuales; `acknowledge` exige que esa revisión siga vigente y el grupo esté disponible. Estas funciones están en fuente con gate de publicación aprobado. No se desplegaron DB022–023. El registro inicial ya coteja transformaciones contra su cadena de recibos, sin aceptar cambios arbitrarios de identidad o estadísticas. La secuencia nativa retirar/recrear conserva aceptación visual pendiente. No se modifican definiciones de hechizos ni su ejecución.

Gate ampliado de publicación: **21 pruebas PostgreSQL aisladas OK**. Incluye snapshot tras movimiento, rechazo de ACK con revisión obsoleta o grupo en combate, ACK idempotente e independencia de eventos de un mismo grupo. `reconcile_seed` valida la cadena de recibos desde la referencia original hasta el roster actual, cotejando todas las estadísticas nativas e identidad; permite únicamente diferencias de posición ajenas a maduración. Su gate combinado pasó26 pruebas y ya está conectado al registro inicial. El gate del ciclo completo está en curso.

## Gate integrado y preparación de carga

**49 pruebas PostgreSQL aisladas OK**: reloj, intentos, recuperación, ciclo/publicación, grupos persistentes, movimiento y grupos Redis. Se verifica retirada12304 antes de recreación12608 con los mismos UIDs, una publicación por grupo, pausa en ausencia/combate y reintento tras excepción del emisor. La recepción efectiva del cliente sigue pendiente. Imagen `3d56c5aba3b2d031c48a977f41238536d9c40bcd00684d6da3a5ee69b970863f` construida; backup privado previo guardado. No se reinició ni desplegó todavía.

Optimización previa a carga: `observe` inserta y actualiza relojes por lote. Gate ampliado **53 pruebas PostgreSQL OK**, incluyendo contador de consultas: cinco por zona con100 referencias madurables, seis si hay eliminación de un reloj terminal; ausencia solo ejecuta una actualización de anclas no nulas. Se preservan exclusiones, intervalos congelados y ciclos únicos. Imagen actual construida `07868f2a7b055df01f8e7e07af4c0fbf73d71b75de41c984742a290b5da5069b`, todavía sin recarga.

## Despliegue — 6 de octubre

**Cambio hecho no confirmado.** Imagen07868f2a recargada después de comprobar cero combates/ocupaciones y política de plantación restaurada. Startup aplicó DB022–023; Docker y `/health` están saludables. Falta aceptación visual del cambio de forma y continuidad en partida. Las notas previas de no despliegue son históricas.


## Confirmación visual y comprobación pendiente

El cliente de prueba confirmó la transformación de Bebé Tofu (referencia6, nivel4) a Tofu (referencia4, nivel8) conservando el actor−88006001. La reentrada mostró exactamente una entidad con esa identidad, sin duplicación. Las capturas y el cotejo de paquetes se conservan de forma privada en `.runtime/local/instances/audit-profession-013/e2e-tofu-maturation.json`.

El servidor actual utiliza la imagen `f7599765` y migraciones hasta025; el gate integrado de105 pruebas PostgreSQL/Redis pasó. Falta comprobar visualmente el mismo actor después del reinicio del servidor: el token del perfil había caducado y fue renovado sin cambiar políticas ni hechizos. Estado: **Cambio hecho no confirmado** para el cierre completo.


## Reentrada después de reiniciar servidor confirmada

El perfil de prueba reentró y encontró exactamente una entidad con actor−88006001, grupo88006001 y una sola membresía PostgreSQL. El paquete12608 del6 de octubre12:17:35 UTC publica Gorditofu, referencia704, con esa misma identidad. Los recibos de maduración22 (4→5) y28 (5→704) explican el avance posterior; no se recreó ni duplicó el monstruo. Captura privada: `.runtime/local/instances/audit-profession-013/e2e-tofu-restart-reentry.png`. La persistencia tras reinicio queda comprobada para esta trayectoria; no certifica aún todas las familias ni etapas especiales.

Migración035 desplegada2026-10-06:runtime confirma900000ms. Gate92 específico cubre límites por etapa, pausa y reinicio de temporizadores sin perder recibos; gate final397 en imagen366629bb OK. Usuario pide continuar otros issues; no se solicita otra prueba pequeña de maduración.
