# Pruebas y límites

## Ejecutado

- Lectura de unidad y hoja del personaje aportado, sin escribir DB.
- Exportación de los 40 modelos `aMo`; identificación de las cuatro referencias/modelos de dragopavo, salud y velocidad.
- Ejecución del lector/escritor nativo `rw`: `0000` restaura ausencia; montura presente sin mascota consume 26 bytes y conserva los seis i32.
- Lectores nativos de 12634 para los ocho resultados y 13928: actor 34 y estado/error correctos.
- Estado `fvN` nuevo con vida máxima: `aqb=true`; reducir vida a cero: false. Inicialización offline con reloj explícito; no prueba gráficos ni alimentación real.
- Cotejo de guardas de `canRide`, equipo persistido, vaciado PET, ausencia de handlers y persistencia mínima.

[Evidencia y hashes](probe-monturas-nativo-y-servidor.json). Sin sesión GUI ni paquetes de la sesión del usuario; no se afirma reproducción completa después de un fix.

## Matriz de aceptación para implementación

| Caso | Resultado exigido |
|---|---|
| Nuevo y existente, sin misión, nivel suficiente | Puede montar su unidad equipada; no se regala item |
| Nivel 34/35 y modulación | Requisito nativo de equipo consistente; sin confundir nivel de montura |
| Equipar, cambiar build, desequipar | PET, item, bonus y botón coherentes; sin reponer vida/XP |
| Montar/desmontar/repetir/spam/reconectar | Resultado idempotente, cooldown persistido, dueño y observador coinciden |
| Unidad ajena, stack, UID inexistente, lease anterior | Rechazo sin consumo ni cambio de estado |
| Vida 0, reposo, muerto, natación, zona prohibida | Rechazo nativo acreditado y sin desincronización |
| Dos jugadores, entrada tardía, teleport/instancia | Apariencia y estado correctos, sin eventos cruzados |
| Rutas iguales a pie/montado y solicitud acelerada | Tiempo por modelo, sin saltos fraudulentos ni PM añadidos |
| Combate, victoria/derrota/rendición/espectador | Transición y retorno coherentes; bonus de equipo no duplicados |
| Comida, curación, reposo y cosmético | Consumo/estado atómicos; fechas y cooldown sobreviven reinicio |
| Reinicio/fallo entre commit y publicación | Estado recuperable; no duplicación de items ni pérdida de montura |

Pendientes técnicos: carrier PET en caliente, estado montado de bootstrap, protobuf rico de item, handlers de alimentación/cosméticos y recorridos GUI/observadores. Son trabajo de investigación/implementación, no decisiones a pedir al usuario.
