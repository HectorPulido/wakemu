# E18 — Motor de IA táctica de enemigos

## Estado actual — 2026-10-07

**Avance aproximado: 85 %.** Base genérica implementada; aceptación manual y
rendimiento con cuatro encuentros simultáneos pendientes. Los ataques sin
implementación nativa no se inventan desde AI.

| Componente | Estado verificado |
| --- | --- |
| World | `3af10843cbc6`, inicio externo `2026-10-07T19:32:35.800276365Z` |
| AI | `26576b10f2bb`, inicio `2026-10-07T20:52:14.414608101Z` |
| Suite final | **459 pruebas OK**, motor actual `3af10843cbc6`; 169 imports nativos, ninguno externo; 116,222 s de validación de la reorganización |
| Pruebas focalizadas nuevas | 60 de búsqueda, caché, entrada y provisión OK (0,114 s) |
| Catálogo vivo | **13.269 entradas**, 711.838.483 bytes declarados en el manifiesto; sellado completo, sin faltantes |
| Reinicios propios de world | **1/3**; ninguno nuevo |

## Organización del servicio

Código en `server/ai-service/wakfu_ai/`, dividido en `planning`, `native`,
`context`, `bridge` y `http`. Pruebas en `tests/`, operaciones en `scripts/`,
mediciones en `benchmarks/`, probes Java en `tools/java/` y documentación en
`docs/`. La raíz conserva únicamente configuración, README y entradas
compatibles que ya consumen world y sus pruebas externas.

El loader estable carga la nueva entrada privada correctamente desde el
world activo; no se modificó ni reinició world. Docker arranca con
`python3 -m wakfu_ai`; `COPY .` y el catálogo completo se conservan.
**Reorganización validada: 459 pruebas OK**, 115,552 s de tests/116,222 s
de validación. Los 169 módulos nativos proceden únicamente del motor
congelado `3af10843cbc6`. Los 104 archivos Python del contenedor AI coinciden
por SHA con el SDK actual; servicio saludable y catálogo sellado completo.
No se modificó el algoritmo, los presupuestos ni el soporte de hechizos.
Evidencia: `.runtime/local/e18-ai-package-layout-final-full-suite.log` y
`.runtime/local/e18-ai-package-layout-final-rebuild.log`.

Estructura y comandos vigentes: [README del servicio](../../../server/ai-service/README.md).

El catálogo completo se prepara antes de dar AI por listo. Una caché privada
persiste snapshots por contenido y firmas de archivo; cada turno sigue
inventariando todas las rutas y detectando cambios. No se recortan datos.
La preparación inicial del catálogo pasó de varios segundos a 0,806 s en
el ensayo individual preparado; esta cifra no es una garantía por turno.

La ordenación de todas las celdas y la preparación de rutas se contabilizan
como preparación de contexto, conservando los límites reales del turno.
El presupuesto predeterminado es **10 s por turno completo**; las consultas
nativas y el cierre cooperativo pueden superar unas décimas ese plazo.

Ensayo nativo terminado sobre la imagen actual, con motor precalentado como
el arranque real, catálogo frío del proceso y NPC inicialmente a distancia.
Contexto íntegro: 7.075 celdas y 24.556 aristas. Fracción de búsqueda **0,25**,
seleccionada para producción tras mejorar respecto al ensayo preparado 0,5.

| Encuentros simultáneos | Ataques | Movimientos | Tiempo por turno |
| --- | --- | --- | --- |
| 1 | 2/2 | 2/2 | 6,788–7,052 s |
| 2 | 4/4 | 4/4 | 7,745–8,071 s |
| 4 | 6/8 | 8/8 | 8,134–9,686 s |

Sin fallback ni fallos de invariantes. Son 14 turnos privados, no una garantía
de latencia ni aceptación en cliente. Con fracción 0,5, el ensayo preparado
anterior consiguió 2/2, 4/4 y 1/8 ataques. Evidencias:
`.runtime/local/e18-native-prepared-flat-owner-live-turns.json` y
`.runtime/local/e18-native-prepared-quarter-search-owner-live-turns.json`.

El encoder y lector fragmentados están implementados y probados, pero su
activación fue descartada por rendimiento: el ensayo nativo produjo ataques
1/2, 4/4 y 0/8, con un máximo de 23,593 s. Permanece desactivado.
Evidencia: `.runtime/local/e18-native-parts-owner-live-turns.json`.

El primer Wonejo que pasó por timeout fue reproducido y se corrigió la
preparación del catálogo. Sigue pendiente repetir una pelea real nueva y
confirmar el primer turno. La prueba general está al final de este documento.

**Cierre de esta fase por la instrucción del usuario de detenerse cuando el
siguiente avance deje de ser rentable sin los hechizos.** La base genérica queda
desplegada; no se añaden comportamientos ni efectos especulativos. Retomar
roles y balance con repertorios nativos nuevos. La aceptación manual y el
rendimiento con cuatro encuentros siguen pendientes: no se considera E18
completo. La suite final terminó en el proceso49315; evidencia:
`.runtime/local/e18-ai-prepared-search-current-world-full-suite.log`.
Reconstrucción y provisión final: proceso84281 terminado exit0,
`.runtime/local/e18-ai-final-quarter-search-rebuild.log`. Revisiones anteriores:
[historial de validación](HISTORIAL-VALIDACION-HASTA-20261007.md).

## Alcance y reglas vigentes

- Todo cambio de lógica se hace en `server/ai-service`; documentación E18
  y artefactos de validación también están autorizados.
- Puente genérico v3 ya integrado una vez: no añadir campos o lógica a world
  para cada hechizo. El SDK completo se monta read-only y mantiene las
  consultas/ejecuciones en el hilo propietario del combate.
- Server entrega **todo** el contexto, fuentes, catálogos, autoridades y
  campos futuros. No hay recortes de monstruos, habilidades, mapas o datos
  para ajustar el tamaño de un paquete.
- **Arquetipos y capacidades genéricos**. Ninguna regla por nombre o ID de
  monstruo. Solo mecánicas explícitas de tipo puzzle admiten excepciones.
- Una sola versión activa de AI; reinicios de AI autorizados. Dockerfile
  conserva `COPY .`, con el catálogo completo de la imagen viva de world.
- Cliente, porcentajes de drop y checkpoint de persistencia quedan fuera
  de este trabajo. Preservar los cambios de los agentes de world.
- Máximo 3 reinicios propios de world en total, avisando antes. El tercero
  cierra también la autorización para seguir editando archivos.

## Implementado y comprobado

El servicio genera candidatos y compara resultados de previews nativos:
movimiento, lanzamiento, soporte, control, orientación y coordinación.
No replica fórmulas de daño ni inventa legalidad. Conserva alternativas y
replanifica tras cada acción ejecutada; los planes no son órdenes ciegas.
Los perfiles y capacidades permiten combinar afinidades, sin encerrarlas
en una sola etiqueta ni construir árboles por especie.

El puente conserva runtime y actores completos, builds/decks, invocaciones,
fuentes de autoridad, topología XYZ dirigida y callbacks como descriptores.
La ejecución nativa conserva FIFO y la barrera real de ACK. Los snapshots
privados, checksum, alias y ciclos se verifican; una dependencia obligatoria
no soportada se declara explícitamente.

Últimas correcciones:

- Build predeterminada 0 sin fila SQL: el adaptador usa `catalog_indices` y
  `default_deck` nativos, sin fabricar registros. Verificado read-only con
  el personaje real 10: build 0, filas guardadas [], catálogo [0], deck 24 bytes.
- Encoder y cachés de geometría conservan bytes completos y distinguen
  objetos iguales con identidades diferentes. Los campos futuros hacen
  usar el camino completo cuando no son elegibles para un cache.
- Publicación de snapshots comprimidos directamente por bloques: elimina
  la consulta previa redundante. Duplicados conservan el archivo verificado,
  corrupción se repara con checksum completo y ACK perdido se reintenta.
  El deadline se comprueba antes/después de comprimir.

## Diagnóstico del Mimic reportado

Combate 23: Mimic HP 1, PA 0, PM 3, WP 0, posición `[-23,16,-8]`; rival
`[-23,17,-9]`. Ya estaban adyacentes. Los cinco Mimics del catálogo vivo
conservan `native_abilities=[]`. Los dos movimientos comparados gastan 2 PM
sin reducir distancia:score −0,2 frente a 0 por pasar.

Antes, el rechazo de la build 0 impedía siquiera buscar; eso está corregido.
La ausencia de ataques y la lentitud de consultas son problemas distintos.
No se inventará un ataque ni una regla de huida del Mimic. Una conducta de
retirada deberá proceder de un arquetipo/capacidad y utilidad genéricos.

## Próximo trabajo

1. Suite final y despliegue verificados: 459 pruebas OK, 60 focalizadas OK,
   AI saludable; hashes de búsqueda, entrada, puente y provisión iguales al SDK.
2. Confirmar una pelea manual completa: primer turno, acercamiento, ataque,
   muerte de un enemigo, resultados y segundo encuentro sin memoria obsoleta.
3. Dejar documentada la limitación de concurrencia: 6/8 ataques con cuatro
   encuentros no acreditan aceptación completa ni un SLA.
4. Retomar corpus real de roles y balance cuando existan más hechizos nativos.
   Los nuevos repertorios entran automáticamente; no ampliar el puente ni
   añadir reglas por monstruo para suplir ataques ausentes.

El formato fragmentado tiene encoder, lector y transporte completos, pero
queda **desactivado** tras empeorar el ensayo nativo. No es un pendiente de
activación ni una razón para prolongar esta fase.

## Prueba manual general

En Amakna, mapa 1134, instancia 0:

1. Escribir `!pos` y comprobar mapa/instancia.
2. Escribir `!mob 5525 1 2`, atacar al grupo de dos Wonejos de nivel 1,
   colocar el personaje a varias celdas y marcar Listo.
3. Pasar varios turnos: deben moverse por celdas libres con PM descontados
   y atacar cuando su habilidad nativa tenga un blanco legal.
4. Adyacente a un Wonejo: como máximo un lanzamiento por turno sobre el
   mismo blanco, conforme a su límite nativo; sin daño o recursos gratis.
5. Derrotar a uno: el superviviente debe usar el roster actualizado.
6. Terminar la pelea, comprobar resultados y empezar otra: no debe
   arrastrar foco ni acciones del encuentro anterior.

Pasos y evidencia de FIFO/ACK en la
[prueba completa de world](../../../server/ai-service/docs/PRUEBA-WORLD.md).
Los ataques aún no implementados por el motor común no se simulan desde AI.

## Diseño y evidencia

[Servicio](../../../server/ai-service/README.md) ·
[Validación](../../../server/ai-service/docs/VALIDACION.md) ·
[Inventario del puente](../../../server/ai-service/docs/BRIDGE-INVENTORY.md) ·
[Catálogo Docker](../../../server/ai-service/docs/CATALOGO-CONTENEDOR.md) ·
[Pendientes](FALTANTES.md).

[Cotejo con Dofus sin Laya](COTEJO.md) · [Solución](SOLUCION.md) ·
[Contratos y algoritmo](CONTRATOS-Y-ALGORITMO.md) ·
[Etapas](PLAN-DE-IMPLEMENTACION.md) · [Casos de aceptación](PRUEBAS.md).

Prioridad 6 del índice general; dependencias: motor común de hechizos,
rendimiento 0, combate compartido/instancias 14/15/29 y configuración E01.
