# 6. Cardo no llega a su etapa final

Recorrer todas las etapas válidas de una planta y conservar el progreso.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**En revision.** El servidor ya utiliza el grafo PostgreSQL de migración017: 401 aristas para141 referencias vegetales, más cinco referencias con etapa1 terminal. Está desplegado; falta completar la aceptación visual y el recorrido automatizado de todas las especies. Las notas anteriores a017 se conservan como historial.

## Dependencias

5, 20, 27 y almacenamiento adicional. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Solo crece un recurso existente por una arista legal; un temporizador antiguo no recrea lo cosechado.

## Comprobación de etapas y acciones

[Scheduler detenido en 2 y tabla nativa de acciones](REVISION-RESPUESTAS.md).


## Política actual cotejada

99 referencias recorren1→2→3→4, 32 recorren1→2→3 y10 llegan a5; cinco permanecen en1. Los plazos por arista se guardan en PostgreSQL. El scheduler usa tiempo de pared en todas las zonas, incluso sin jugadores, y procesa una arista vencida por recurso y ciclo; una ocupación de cosecha vigente impide avanzar ese recurso. No aplica todavía un modificador climático. Esto describe el comportamiento implementado, sin acreditar reglas oficiales ni la aceptación gráfica completa.

El modo abierto de plantación omite territorio familiar y aptitud del suelo, incluso suelo0; conserva resolución de altura y ocupación. Las pruebas de permisos territoriales deben cubrir por separado el modo nativo. Se está ampliando la regresión a todas las trayectorias del catálogo.


## Regresión exhaustiva del catálogo — 6 de octubre

`test_every_seedable_resource_follows_each_filtered_catalog_stage_with_stable_uid` recorre las146 referencias vegetales plantables con reloj controlado. Comprueba las401 aristas, la etapa persistida, paquete12782 con coordenadas y propietario público0, el outbox confirmado y la misma identidad del recurso. Las cinco referencias sin aristas permanecen estables, y ninguna referencia avanza después de su etapa terminal. El módulo `test_plant_growth_graph` pasó **12 pruebas** en PostgreSQL aislado. Esto acredita el grafo local configurado; no demuestra modificadores climáticos ni el comportamiento visual de todas las especies.

## Aceptación parcial en cliente — 6 de octubre

El Cardo60 de auditoría UID2940413456108495712 avanzó1→2→3→4 mediante el worker activo; después de reentrada, el paquete13135 mostró etapa4 y propietario público0. Fresno139 UID7631321523612460859 apareció en etapa4 tras reentrada y permitió talar. Ambos concedieron sus productos y50XP de oficio. Son recursos preparados como fixtures, no éxitos de plantación nativa. La cobertura automatizada del grafo sigue siendo146 referencias; la evidencia visual corresponde a Cardo/Fresno y no sustituye validar otras especies ni clima.

## Regresión de variante especial — 6 de octubre

El usuario confirma que todos los cardos terminan como Cardo tornasolado y solo ofrecen Talar. Catálogo60: etapa3 ofrece acción203 (cardo normal2504) y acción100 (semilla4275); etapa4 ofrece solo1475 (especial11447). Migración017 fuerza3→4 tras30s: el grafo ordinal confundió madurez normal con variante especial. Los gates anteriores comprobaban la ejecución de ese grafo, no su corrección semántica; no acreditan el comportamiento esperado. Investigar criterios nativos y separar madurez normal/variante especial para todas las especies, con probabilidad persistida configurable. No resolver ampliando las acciones de la etapa4 en el cliente.

## Corrección probabilística en fuente

Migración032 agrega probabilidad a las transiciones y recibos durables de decisión por UID/etapa. Cardo3→4 se configura con0.01 como política local explícita, no tasa oficial. Si la decisión rechaza la variante, la planta permanece en etapa3; ticks, reinicio y concurrencia no vuelven a tirar para convertir eventualmente todos los cardos. La decisión y el cambio/outbox aceptado comparten transacción. `Plantings.mature` permite RNG inyectado para comprobar ambas ramas. Pendientes gates y despliegue; cardos especiales existentes conservan su identidad.

El cotejo nativo encuentra el mismo patrón normal/semilla en Fresno139 (etapa3 acciones99/538; etapa4 acción930), pero no demuestra un scheduler o probabilidad universal. No se extrapola la rareza de todas las etapas4/5 sin evidencia. El issue permanece En revision.

## Despliegue032 y aceptación pendiente

Imagen9d1b73a0 desplegada el6oct; runtime confirma32 migraciones aplicadas y código de crecimientoSHA256 f06b71c3cef33844c4de843a6340e939cd8c99e8861abe7e438f0ccc8d78d715. Gate de imagen48/48 PostgreSQL aislado, incluidos Cardo/Fresno, decisión persistente, frontera/RNG inválido, rollback y no reroll. Backup correcto de wakemu_runtime antes del despliegue en `.runtime/backups/pre-flora-growth-032-20261006.dump`. No cambios en módulos de combate posteriores al arranque anterior.

Aceptación normal preparada: plantación100% y probabilidad de variante0 para60/139 temporalmente, de modo que la prueba no dependa del azar. Tras aceptar, restaurar probabilidad0.01 de variante, probabilidad0.01 de plantación y política ecológica original. Los cardos especiales ya existentes permanecen especiales; probar nuevas plantas. Estado del issue completo continúa En revision por otras especies/clima, con corrección60/139 Cambio hecho no confirmado.

## Cobertura del catálogo ampliada

Cotejo nativo de ítems (`aLO → bIJ.f → bJp.dAX → fof`) identifica88 referencias con producto normal UNUSUAL y producto posterior RARE. Clasificación reproducible guardada en `server/protocol/flora-variant-classification.json`. Migración033 amplía la política local opcional a86 referencias adicionales; no altera60/139 ni sus pruebas temporales. Excluye825 (mismo producto UNUSUAL en ambas etapas) y843 (productos normales de rareza mixta). Las probabilidades siguen siendo políticas del emulador: el catálogo demuestra rareza, no una tasa de transición. Gate combinado68 PostgreSQL aislado OK: matriz88 referencias, actualización de86 adicionales, exclusión825/843, conservación de pruebas temporales60/139 y de recibos existentes al aplicar033. La033 todavía no está en imagen ni DB runtime; despliegue pendiente.

## Confirmación del usuario y política ampliada

El usuario confirma que el cardo normal funciona y que Herbolario sube correctamente. Logs acreditan acción100 de extracción aplicada, población sin cambios, reentrada de Audiluna y cosecha normal201 aplicada. SQL conserva plantas nuevas en etapa3 con una decisión de variante rechazada, sin repetir tirada. Cardos especiales anteriores permanecen en etapa4.

033 aplicada a wakemu_runtime en caliente (sin reinicio):33/33 migraciones,88 aristas con probabilidad opcional,60/139 continúan a0 temporal para la prueba. La etiqueta preparada para un futuro recreate es imagenf7546cfa; contenedor actual continúa con imagen9d1b73a0 y carpeta de migraciones actualizada con033. No confundir etiqueta preparada con recreate efectuado.

Política ecológica temporal±500 y límiteCardo4 retirados; política original±25 y fallback vegetal0..100 restaurados. Se conserva el valor ganado por el personaje. Plantación100% y variantes60/139 desactivadas siguen activas para terminar la aceptación de Fresno. Prueba completa de Fresno ya enviada con comando8063 y expectativas de esquejes/madera/reentrada.

## Verificación automática integral adicional

7 de octubre: gate PostgreSQL aislado69/69 con test_flora_planting_harvest_e2e, planting_runtime, plant_growth_graph y resource_harvest_completion. Fresno139/Cardo60 se prueban desde semillas, autorización ecológica normal, crecimiento1→2→3, semillas, regeneración, cosecha terminal/remoción, replantación en misma celda conUIDnuevo y Store.reopen/snapshot persistente. Política global intacta; se fija solo la tirada para éxito reproducible. Cierra el hueco de fixtures previamente iniciados en etapa madura; aceptación visual del fresno por flujo normal y clima adicional permanecen pendientes.
