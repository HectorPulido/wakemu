# 7. No sube Wakfu ni Stasis

Actualizar el estado ecológico personal por acciones válidas con reglas explícitas.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Solucionado totalmente.** La integración vegetal y los nacimientos de monstruos plantados están desplegados en world healthy, imagen a08ba92c, esquema034. Plantación, tala/cosecha que retira población y extracción neutra comparten recibos y actualización de afinidad con la acción confirmada. La fórmula usa puntos básicos: mejora la distancia a equilibrio=+0,25 puntos porcentuales; empeora=−0,25; distancia igual=0. El mensaje nativo Información (juego) explica población antes/después, rango y afinidad; solo lo recibe el actor.

Gates de la imagen:75 ecología/INFO;83 posición/Redis/wire/social (9 skips);24 selección/builds/social. Audiluna mantuvo el porcentaje previo al migrar (DB6077bps, mismo wire675 y revisión32). La aceptación visual de la fórmula y los mensajes está pendiente.

Retirada de monstruos por victoria: implementación desplegada en 3540c61b participa en la transacción de cierre/recompensa del grupo, con recibos por región/familia. No altera hechizos, daños, IA ni turnos. Gate final de imagen246 OK; aceptación visual pendiente. La reproducción natural no tiene responsable y no premia a un personaje arbitrario. Árboles, plantas y cultivos usan el mismo conteo vegetal por familia/región; la prueba completa de Fresno y demás especies sigue pendiente.

## Dependencias

1, 3, 5, 28. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Solo acciones confirmadas alteran progreso una vez; los valores pertenecen al personaje correcto.

## Historial de despliegue y aceptación controlada — 6 de octubre

El despliegue d875e168 incluía un buffer que requería `characters.direction`, pero solo empaquetaba migraciones hasta028. La selección de Audiluna falló con `KeyError: direction`. La imagen anterior también tenía esa dependencia incompleta. Se aplicó029 y se preservó el historial de migraciones; logs del servidor confirman selección correcta de Audiluna el6oct18:35:30UTC. Imagen de recuperación8705102. Esto repara la entrada, sin acreditar el lote ecológico nuevo.

Candidato bc0f1feb: d875e168 más migración029, sin añadir los cambios posteriores de grupos o población inicial. Pendiente de gate contra el código de la imagen y posterior despliegue. No se considera suficiente el health HTTP para validar selección.

La prueba anterior quedó al1% al restaurar las políticas durante la reparación: el usuario confirma que ninguna de sus plantaciones arraigó. Se volvió a fijar temporalmente la probabilidadSQL a1. Los deltas±500 y el límite local deben prepararse nuevamente después del despliegue correcto. Política original guardada en `.runtime/backups/ecology-visual-policy-20261006.json`; restaurarla al terminar. No se acredita como backup de runtime el dump previo dirigido a otra base de datos.

## Evidencia manual posterior a recuperación

Usuario confirma cinco plantaciones:15% Wakfu; después corta dos cardos:21% Wakfu. SQL acredita exactamente revisiones1–5 por plantación (valor0→125) y6–7 por retirada (125→175), cada acción+25, sin duplicados. Ambas retiradas clasificadas equilibrio con fallback mínimo0/máximo100, poblaciones6→5→4. Esto confirma que la imagen de recuperación sí contiene la integración vegetal; no inferir su ausencia por la etiqueta de imagen anterior.

Prueba histórica temporal (ya retirada): Stasis preparada con población Cardo4, límite local mínimo=máximo4 y deltas±500; valor inicial175. Cortar uno debe dejar325 unidades negativas (aprox36% Stasis); volver a plantar uno devuelve175 (aprox21% Wakfu). Plantación temporal100%. Restaurar políticas originales al finalizar. Aceptación pendiente de confirmación visual, recuperación y otras ramas.

## Contrato real de despliegue

Compose monta `local_game_server.py`, `protocol_codec.py`, `wakfu_server/` y `protocol/` desde el checkout. Por tanto la etiqueta Docker no identifica por sí sola el código activo: el proceso carga esos archivos al arrancar, mientras las migraciones pertenecen a la imagen. La regresión de entrada demuestra la necesidad de verificar ambos lados del contrato. Despliegue9d1b73a0 incluye migraciones1–32; comprobación posterior32/32 y hash del módulo de crecimiento activo registrado en issue6. Los módulos de combate no fueron modificados en este lote.


Afinidad gradual e Información (juego) desplegadas en SQL034/imagen a08ba92c: pasos±0,25pp según distancia a banda, extracción y plantación fallida sin recompensa; mensaje con población, límites y afinidad antes/después tras commit. Gates de imagen75+83 (9 skips)+24 OK, world healthy. Audiluna conserva porcentaje anterior (wire675, DB6077bps, revisión32). Pendiente aceptación visual; estado En revision por alcance restante del issue.

Verificación final 2026-10-06: imagen3540c61b, 246 pruebas OK; Docker healthy y entrada de Audiluna confirmada en logs a20:34:05 UTC. Arranque previo a listeners: catálogos24,46s y validación de población14,75s; durante ese intervalo no admite conexiones. Aceptación visual del ecosistema pendiente.

Aceptación manual de alcance completo: [PRUEBA-COMPLETA.md](PRUEBA-COMPLETA.md), con comandos para cardo/fresno/trigo/Tofu, extracción neutra, retirada, nacimiento, victoria y reconexión.

## Aceptación del usuario — 2026-10-06

Usuario confirma que Wakfu/Stasis funciona tras la prueba del sistema completo. Los deltas ya están parametrizados en PostgreSQL: fila `settings.name=personal_ecology_policy`, campos `balance_delta=25` e `imbalance_delta=-25`, unidad `basis_points`. Un punto porcentual equivale a100 puntos básicos;25 equivale a0,25pp. `ecology_policy.evaluate` lee la fila al evaluar cada acción; no requiere recompilar ni reiniciar para cambiar los incrementos. Consulta del runtime confirma esos valores. Los pendientes visuales históricos quedan superados por esta aceptación.
