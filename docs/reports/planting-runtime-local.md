# Siembra y crecimiento en el servidor local

`Plantings` mantiene ocupaciones por personaje y generación de sesión. `begin` valida semilla propia, acción nativa, casilla autorizada y reserva; `complete` acepta el formato real de `13429` (resultado byte y tipo short 2), comprueba duración y consume una semilla en la misma transacción que crea el recurso. La repetición no vuelve a consumir. `cancel` está limitado a la generación indicada.

`12815` inicia la ocupación con animación nativa 5 para plantas y 47 para reproducción de monstruos. La duración de 3000 ms es una política local explícita. `13135` crea recursos propios y `12954` actualiza la semilla consumida: no se añade una segunda retirada mediante `12470`. `snapshots(map,instance)` sólo reconstruye recursos persistidos de esa instancia.

`open_test_policy=True` permite saltar nivel mínimo y criterios de la semilla en este experimento. Conserva selección de personaje, sesión, propiedad del objeto, identidad de acción y comprobación de casilla que aporta el llamador. El agente del cliente para mostrar cualquier suelo como apto es una pieza separada.

`mature(groups, authorize_spawn=callback)` aplica crecimiento local después de 30 segundos. Plantas con etapa nativa 2 cambian mediante `12782`. Semillas de monstruo retiran el semillero mediante `12782` etapa 0 y registran un grupo propio antes de enviar `12608`. La especie se selecciona por familia nativa y menor nivel, prefiriendo especies que permitan recolectar esa misma semilla. Es una regla local; no representa tiempos ni distribución del servidor oficial. El llamador debe excluir jugadores y grupos que ocupen la casilla.

Una bandeja persistida en SQLite conserva publicaciones pendientes cuando Redis falla. Reintentar no consume otra semilla ni crea otro identificador de grupo. La casilla queda reservada mientras falte publicar. Los mensajes se devuelven agrupados por mapa e instancia para que el servidor los distribuya.

Los lectores Java reales `cyK` y `cAx` aceptan los cuerpos de inicio y cambio de etapa. La retirada visual se sustenta en la cadena `cFJ → bOm → bOw → bOv`: los recursos temporales marcan retirada al terminar la animación de desaparición. La prueba gráfica aislada requiere JNI y no se ha ejecutado; no se presenta como comprobación visual del cliente.

`profession_store.ensure_learned` persiste oficios propios con nivel inicial 0 y emite `12675`. Preserva niveles guardados. No calcula XP ni inventa progresión de oficios. La cosecha de plantas mediante `12995` sigue pendiente de extracción de acciones, cantidades y condiciones nativas; sembrar y madurar no equivale todavía a completar toda esa cosecha.

Validación: 11 pruebas de siembra, ocupación, consumo, generación de sesión, permisos de oficio y recuperación de publicación. No se modificaron cuentas de usuario, ni se reiniciaron servicios, ni se realizaron conexiones oficiales.
