# 10. No hay drops ni kamas

Entregar botín y kamas configurables, sin duplicación ni pérdida cuando falta espacio.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

🟡 **Solucionado parcialmente — drops y kamas con máxima prioridad por instrucción del usuario.** La configuración anterior concedía0kamas por victoria; la política SQL activa calcula límites y sorteos durables. Se implementa la fórmula Dofus con límites y tasas SQL, un sorteo durable y actualización visible de wallet. Los drops proceden del catálogo del cliente Wakfu: objetos, probabilidades y condiciones propias, incluyendo intentos individuales cuando lo indique. La captura del usuario muestra sombrero de jalató0,8%, un intento por jugador y sin condición particular. Migraciones041–043 y callbacks conectados: XP/kamas, tiradas nativas y entrega en bolsa o temporal comparten la transacción; bootstrap y solicitudes13993/12294 recuperan los excedentes. Gate combinado de91 pruebas aprobado en fuente. Imagen9af0658c (`wakfu-local-world:merged-verified`) desplegada y saludable;200 pruebas de imagen y smoke nativo integral aprobados. Migraciones001–048 aplicadas; conserva la IA activa. Pendiente [aceptación manual](../09-experiencia-de-combate/PRUEBA-GENERAL-RECOMPENSAS.md). Drop×1 restaurado; prueba usa Mimic4196, cuyo premio12325×3 es nativamente garantizado. Los criterios complejos, tablas externas, clasificación de mazmorras y alcance de rollMax siguen en revisión; no se declara resuelto el sistema completo.

## Dependencias

Instrucción adicional del usuario: aplicar también al drop la fórmula Dofus de referencia, manteniendo objetos, tasas base y condiciones del cliente Wakfu. El multiplicador de drop se configura en PostgreSQL; no se cambia el catálogo base para aumentar la tasa.

El usuario excluye modificar el cliente para mostrar porcentajes ajustados: la enciclopedia conserva sus porcentajes base nativos. El multiplicador se aplica en el servidor y se verifica mediante las recompensas concedidas.

9, 11, 22, 32 y 0. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Resumen=recibo=wallet/inventario; cada UID otorgado y cada kama se entregan una vez.

## Ampliación automática desplegada

Fuente validada contra PostgreSQL aislado:54/54 pruebas de políticas, drops, entrega y migraciones. Conserva cada fila nativa de botín, incluso referencias repetidas; mantiene vinculación al recoger en bolsa/temporal y evita entregar objetos en bolsas con filtros no satisfechos. Esta ampliación está incluida en el merge9af0658c. Su aceptación visual sigue pendiente.

Imagen candidata b33fe0e4:75/75 pruebas de módulos de imagen y recorrido completo por socket aprobado. Posteriormente se integró en world9af0658c junto con recuperación agrupada, Obtenerlo todo, abandono y reciclaje de objetos temporales. Los módulos de combate coinciden byte a byte entre ambas imágenes.

## Aceptación manual del merge

El usuario confirma «Todo funciona bien» en la prueba general. Al abrir conservaba el último botín en espera y pudo recuperarlo; captura: botín en inventario y489kamas. Recuperación/Obtenerlo todo, reciclado, abandono y persistencia confirmados dentro de esa prueba. Permanecen pendientes criterios complejos, tablas externas, clasificación de mazmorras y rollMax.

## Cotejo adicional de tablas externas

Lectura directa del catálogo instalado:2204 tablas externas, pero cero enlaces is_loot_table en las filas combat_drops de los monstruos exportados. La existencia de esas tablas no demuestra que correspondan a recompensas de combate; se debe identificar su productor nativo antes de conectarlas. No se inventan asociaciones por referencia o parecido.

## Impacto de condiciones pendientes

[Conteo reproducible del catálogo](probe-condiciones-catalogo.json):3069 ocurrencias de MIN_STASIS_LEVEL,634 de Stele,268 de score,212 solo mazmorra,177 fuera de mazmorra,160 de nivel modulado y134 fuera de oleadas. Hay686 filas con criterio complejo. Los conteos pueden coincidir en una misma fila y no equivalen a objetos únicos. Contexto de nivel modulado desplegado en3523a0a5;8 pruebas de contexto y smoke nativo de combate/recompensas aprobados. Priorizar fuentes autoritativas para Stasis/mazmorra; no habilitar condiciones ausentes por defecto.

## Dependencia de mazmorras para Stasis

Las151definiciones de mazmorra nativas no representan una ejecución activa. El Fight actual y SharedFight no conservan dificultad/Stasis seleccionada ni sesión dungeon; el ID temporal de colocación tampoco la identifica. MIN_STASIS_LEVEL requiere una sesión de instancia autoritativa del issue29, congelada al iniciar el encuentro. No se confunde con afinidad ecológica ni daño elemental Stasis. Se revisa por separado si la ruta de encuentros ordinarios permite acreditar las condiciones negativas de dungeon/oleadas.

La [auditoría de cobertura del catálogo](AUDITORIA-COBERTURA-DROP.md) cuantifica lo pendiente:686 de16.138 filas con criterio complejo,1.343 con límite nativo1 y ninguna fila de monstruo enlazada como tabla externa. No confundir las2.204 tablas externas exportadas con una dependencia demostrada de estos drops.

La semántica de `native_csE` (`m_rollMax`) sigue sin estar resuelta: el cliente instalado lo carga y conserva, pero no se encontró un ejecutor de tiradas que defina ámbito o reinicio. El resolver conserva el campo, sin aplicarlo como límite. Ref. 5767 (`Mekarbok perturbado`, nivel10) con ref.32426 ofrece una fila garantizada sin condiciones exportadas, pero su mapa y si aparece como enemigo ordinario o invocación no están acreditados; todavía no es una prueba oficial lista para pedir. Evidencia y plan discriminante: [auditoría rollMax](../../reports/wakemu-drop-rollmax.md).

Revisión JAR 2026-10-07: `csH` elige en el tooltip la etiqueta genérica de criterio complejo y oculta la lista `csG`; cinco de esas filas aún exponen MIN_STASIS_LEVEL, pero no la expresión completa, así que siguen fail-closed. `csE`/`m_rollMax` se copia al modelo, pero el cliente instalado no contiene consumidor de tiradas que defina cap, ámbito o reset; no se interpreta como límite. La prueba mantiene explícitamente ese límite desconocido y comprueba que `roll_count`, no `csE`, determina los intentos implementados.
