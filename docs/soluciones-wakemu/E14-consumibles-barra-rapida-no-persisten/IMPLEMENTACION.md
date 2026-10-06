# E14 — Implementación del servidor

Se añadió world_shortcuts.py con decoder12091 completo y serializer nativo so/sq/yv/yw/yu. Límites cotejados: WORLD4×8, FIGHT4×6, SYMB1×8; coordenadas relativas. El decoder conserva explícitos los dominios distintos de WORLD sin alterar hechizos. La colección WORLD conserva cuatro barras incluidas las vacías para impedir desplazamientos. Se rechazan coordenadas inválidas y asignaciones duplicadas; una eliminación seguida de asignación es reemplazo. Pruebas de codecs delegadas a Luna.

Faltan tabla PostgreSQL, validación de propiedad/catálogo de los descriptores, handler y carga de colección en bootstrap. Esta pieza todavía no corrige la persistencia de barra por sí sola.

## Dominio, tabla e integración

Migración005 agrega character_world_shortcuts con FK de personaje, PK barra/slot y checks nativos. El handler12091 decodifica todo antes de mutar, valida lease/ownership y todos los descriptores WORLD antes de ejecutar removals/asignaciones en una transacción. Un reemplazo elimina y asigna la misma clave; replay mantiene los mismos valores. Referencias requieren catálogo utilizable y existencia propia al asignar; UID exige entidad propia y referencia coincidente. No concede ni consume objetos. FIGHT/SYMB se decodifican pero quedan fuera de esta mutación; no modifica decks.

Store.character carga el estado durable y minimal_entity serializa SHORTCUT_INVENTORIES. Referencias se conservan al agotar unidades; accesos UID sin entidad propia no se restauran ni se convierten a referencias. Se conserva el descriptor extra sin interpretarlo como permiso. No se inventó ACK: el caller nativo observado no espera uno.

Las cuatro barras del snapshot son el límite WORLD cotejado; el probe Java de tres barras demuestra los predecesores vacíos, no un máximo de tres. Nueve pruebas de codec pasan según Luna; dominio PostgreSQL y bootstrap están ahora pendientes de pruebas y carga. La prueba visual de consumo/reconexión permanece pendiente.

## Verificación delegada

Luna ejecutó codecs/bootstrap, dominio PostgreSQL y migraciones: **18 pruebas pasan** en Docker. Incluye rollback del lote inválido, UID ajeno/referencia equivocada, lease sustituido, reapertura, replay sin mutar inventario, agotamiento y segregación de FIGHT. La restauración por entidad se probó con layout verificado sintético; todavía falta interfaz real. El decoder nativo Java lee el contador u16 sin imponer tres barras y admite el snapshot completo de cuatro.

Replay de referencia confirmado tras consumir la última unidad: se acepta únicamente el descriptor y posición ya persistidos, sin permitir nuevas asignaciones de una referencia agotada. No se concede ni recupera ningún objeto. Construcción/carga Docker en curso.

## Carga en Docker

Se construyó/recreó world y quedó healthy. El entrypoint aplicó005: PostgreSQL principal confirma versiones1–5 y33 tablas. El handler12091 y restauración por entidad están cargados. Luna verificó también auth/Redis/E14 en esquemas aislados: **48 pruebas pasan**, sin sumar este lote solapado al de18. Prueba visual pendiente por la captura no disponible; no se declara aceptación GUI.

## Asignación real y flush del cliente

Luna confirmó visualmente Semilla de trigo ×5 en «Atajo (1)» del personaje nuevo Audiluna; captura privada `69-hover-hotbar.png`. La salida normal al selector (`73-menu-again.png`) produjo persistencia real: `character_world_shortcuts`, personaje1/barra0/slot0, descriptor tipo1, referencia1752 y extra3124278. Antes de la transición no había filas: coincide con el flush nativo cotejado, no con un envío inmediato al arrastrar. Pendiente comprobar la restauración visual tras reentrada y el consumo; no se declara todavía cerrado E14.

## Cierre de persistencia E14

La reentrada normal quedó acreditada en `75-reentry.png`: mapa cargado y Semilla de trigo ×5 restaurada en el primer acceso. Root inspeccionó la captura y cotejó la fila SQL producida por la salida anterior. Con las18 pruebas de codec/dominio/bootstrap y la asignación→flush→reentrada reales, se cierra la pérdida de persistencia de E14. El consumo inmediato de semillas se sigue verificando bajo issue1; no se presenta aquí como prueba gráfica ya realizada. El cierre forzado sin envío de12091 queda fuera de la persistencia de solicitudes que el servidor recibe.
