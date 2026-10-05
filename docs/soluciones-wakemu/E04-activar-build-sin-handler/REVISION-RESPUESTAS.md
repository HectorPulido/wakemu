# Revisión nativa posterior a las respuestas

## Desbloqueo resuelto

La condición `eRg.dO(short)` devuelve oculto cuando nivel ≤50 y visible desde 51. Se ejecutó con 1, 49, 50, 51, 60, 100 y 250. Esto explica por qué nivel 50 seguía bloqueado: no hace falta decidir otro umbral. El cliente usa niveles del roster en `cgY`, `biz.dqi` y la sección CHARACTERS; también consulta el estado `eDS.oUk` al entrar y cuando cambia. La lista y el bootstrap del servidor deben transmitir niveles coherentes; el salto por consola no actualiza por sí solo todos esos modelos.

## Cupo resuelto

`eQZ.fHr()` lee `eEL.pdS`: `NON_PERMANENT_BUILD_LIMIT`, configuración 2510, clave `non.permanent.build.limit`, default 24. `bhp.eH("countAndLimit")` muestra `eQW.fHo()/fHr`; `fHo` cuenta hojas **no permanentes**, no todos los índices. `eQS` contiene 16 tramos permanentes. Se crearon 24 hojas no permanentes en el modelo nativo y se seleccionó índice 3 correctamente. La guarda 0–2 del servidor no refleja ese catálogo.

La solución debe validar cantidad de hojas no permanentes por separado del rango e identidad de índices. No sustituir `index<=2` por `index<=24`: el contador no demuestra ese rango y el protocolo usa un byte con signo. Preservar predeterminada/permanentes y completar todas las colecciones.

## Respuesta de activación resuelta

`ctV.d()` devuelve **13811**. `ctV.dp` lee i64 de personaje y byte con signo del índice: **9 bytes**. El handler `ciu`, caso 13811, llama `eQX.R(id,index)` y actualiza la selección del modelo. Se probó cuerpo sintético ID 1/índice 3; sus getters devuelven esos valores. Un cuerpo de 8 bytes produce BufferUnderflowException. `dp` devuelve false también al decodificar el cuerpo válido; ese retorno no es un status de fracaso.

Esto completa el contrato de éxito que antes estaba sin investigar. 12837 sigue siendo borrado y 12284 guardado; no son ACK de activación. No inventar un campo status en 13811. El orden de refresh efectivo y recuperación ante rechazo debe probarse con el estado optimista real; la búsqueda de strings heroBuildLock no basta para asumir que activar usa el mismo bloqueo que guardar o borrar.

## Cambio concreto del plan

1. Resolver disponibilidad a partir de niveles autoritativos y umbral nativo 51; sincronizar roster/bootstrap al progresar.
2. Definir un catálogo único con clasificación permanente/no permanente, cupo configurable coherente con 2510 y todas las hojas registradas.
3. Decodificar 13776 como identidad e índice; validar ownership, lease, fase, existencia y revisión antes de mutar.
4. Persistir selección y revisión con la autoridad de builds. No activar implícitamente al guardar.
5. Emitir selección **13811** luego del commit, junto con refresh de efectos/hojas en orden verificado. Ensayar que el cliente converge, no solo que el decoder acepta bytes.
6. Reproducir rechazo y reconexión antes de declarar cerrado el flujo. La ejecución de hechizos/decks de combate queda a la otra sesión; no se modifica ni prueba aquí.

## Evidencia y límites

[Resultados estructurados](../34-builds-personalizadas/probe-politica-nativa.json). Los dumps y el probe compilado permanecen privados en .runtime. Se verificaron codecs y política nativa; la ruta 13776 del servidor aún no está implementada y esto no es una activación exitosa de extremo a extremo.
