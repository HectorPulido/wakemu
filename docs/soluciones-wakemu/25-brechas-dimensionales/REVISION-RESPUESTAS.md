# Brechas dimensionales: fuente nativa y límites concretos

## Localización comprobada

La búsqueda literal de `breach` no identifica el sistema en este cliente. Se encontró el menú nativo `cJa.teleportToRift()` → `cgC.TP_TO_RIFT`: sus parámetros son **x=-192, y=-29, mapa 527**. Es una pista de localización procedente del propio cliente, no una autorización de entrada, altura caminable ni prueba de portal funcional. No se ha teletransportado un personaje a una altura inventada.

## Datos existentes

El catálogo `aKU` leído nativamente contiene **7 definiciones INFINITE_WAVE y 3 ULTIMATE_INFINITE_WAVE**. Ejemplo para el exterior 527: definición **168**, interior **1314**, nivel bruto 21. Astrub 1134 tiene definición **174**, interior **1329**, nivel bruto 111. [Metadatos y procedencia](probe-definiciones-oleadas.json).

Esas diez definiciones tienen `cno()` vacío: **no proporcionan por esa vía las composiciones de oleadas**. Tampoco acreditan número de turnos, progresión, cupo, premios o regla de derrota. La coincidencia exterior 527 + acceso Rift hace candidata a 168; todavía falta enlazar el objeto real con su plantilla de instancia. No se afirma que cada tipo infinito sea una brecha convencional.

El catálogo actual `native-generic-teleporters.json` no contiene un destino interior 1314 en sus filas inspeccionadas. No concluir que el cliente carezca del acceso: puede usar otra clase de interactivo o un carrier diferente. `generic_transports.resolve()` rechaza instancias no cero, criterios y plantillas especiales; quitar esos controles no implementa una brecha.

## Solución específica del servidor y siguiente cotejo

Identificar el objeto en (-192,-29) mediante entorno/acciones y resolver su plantilla hacia definición 168 antes de habilitar acceso. Extender la extracción local con el catálogo que describe las oleadas; la lista vacía de monstruos de `aKU` no autoriza llenar el encuentro con mobs genéricos. Mantener los datos derivados privados y reproducibles con la instalación del usuario.

Usar la definición de instancia para reservar participantes y destino 1314, con origen de retorno propio y fase del encuentro. El motor debe registrar índice de oleada y participantes y avanzar mediante eventos confirmados; definir reglas de turnos/derrota a partir del consumidor nativo y fuente autorizada antes de inventar temporizador, cantidad o multiplicadores. Se necesitan contratos específicos para UI de oleadas, finalización y premio: el retorno genérico del combate no demuestra continuidad de una brecha.

Grupos (15), recompensas (9/10) y entradas de instancia (29) son dependencias comprobables, no requisitos cumplidos. Validar desconexión, entrada duplicada y cierre con recibos de progreso/recompensa, sin reutilizar respawn global para simular oleadas.

## Pruebas y límites

Esta revisión cotejó bytecode y catálogo privado; **no hubo combate de brecha ni reproducción GUI**. La búsqueda de destino 1314 fue negativa en un único catálogo, no en todos los datos del cliente. Pendientes: objeto/plantilla, monstruos de cada oleada, reglas y multiplicadores, interfaz, cupo y resultados. No se modificó código ni se implementó ninguna mecánica; issue abierto.
