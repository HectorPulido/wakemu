# Ruta de cierre del combate de clases

Actualizado: 2026-10-05. Alcance de esta ruta: hechizos de clase, pasivas, hechizos extra y armas, con cliente y servidor sincronizados. No incluye completar todo el MMO ni IA y mecánicas particulares de todos los monstruos.

## Evidencia actual

- Última matriz de inicialización y dos cambios de turno: 739/785 ciclos completos, 42 fallos de ciclo, cuatro rechazos de Listo. No hubo regresiones entre los 681 casos antes aprobados. Este resultado NO mide hechizos completos ni porcentaje de proyecto terminado.
- Osamodas200: 18 casos internos de inicialización/pasiva individual y ciclo pasan; no cubren lanzar todos sus hechizos, invocar ni transformar apariencia.
- Usuario confirma Desplume y combate en su escenario. Forma Dracónica se activa pero no cambia apariencia. JamJam rechaza familia325; Invocación rechaza GetSpaceInSymbiot.
- review.json conserva seguimiento manual; las tablas generadas y sus cifras pueden corresponder a fuentes anteriores. Deben regenerarse en cada checkpoint coordinado, sin sobrescribir review.json.

## Orden y criterio de salida

1. **Estabilizar ciclo de combate.** Resolver causas comunes de los 46 fallos restantes: IsOnBorderCell, selector HasState y familia1038. Exigir Ready, cambio manual/automático, ACK, rendición en colocación/combate, victoria, retorno y nueva pelea. Salida: matriz785 sin rechazos inesperados y regresiones de salida aprobadas.
2. **Convertir el harness en barrera para acciones reales.** Ejecutar cada activo, arma y hechizo extra por la misma entrada del servidor; preparar escenarios legales para sus requisitos. Después cubrir pasivas por evento que realmente las activa, no sólo instalarlas. Afirmar daño/cura/armadura/estado/orientación/costes/límites y paquetes entregados. Un rechazo inesperado, un efecto esperado ausente, un bloqueo o un escenario no construido impiden marcarlo aprobado. Salida: todos los casos tienen resultado comprobado o pendiente explícito y reproducible.
3. **Cerrar componentes compartidos por mayor alcance.** Agrupar fallos por causa y contar hechizos afectados antes de asignar. Carriles: valores/eventos/pasivas; objetivos/áreas/zonas; invocaciones/apariencia/sincronización. Primero mecanismos comunes, luego excepciones de clase. Invocaciones incluyen crear, propietario, control, hechizos, turnos, muerte/retirada y repetición; apariencia incluye aplicar y restaurar. Cada corrección repite todos sus dependientes afectados.
4. **Completar particularidades de clase.** Sólo después del componente común correspondiente: Simbiot y hechizos otorgados del Osamodas, recursos específicos, combos, transformaciones y demás reglas individuales. Salida por clase: activos, pasivas y extras pasan los escenarios normales, críticos, límites y retirada pertinentes, sin pendientes ocultos.
5. **Verificación final del cliente y publicación.** Automatizar lo comprobable desde servidor y usar cliente para estados, contadores, apariencia, animaciones, control y baraja. Pedir al usuario pruebas breves priorizadas sólo donde la observación visual añade evidencia. Congelar fuentes, correr regresión conjunta, cargar checkpoint, comprobar salud y registrar huellas de versión. Salida: inventario sin pendientes dentro del alcance y evidencia de cliente para contratos visuales.

## Organización para reducir tiempo y retrabajo

- Un agente por carril con propiedad de archivos; root integra, reproduce incidentes y revisa entrega al cliente.
- Una sola ejecución pesada de catálogo a la vez; fuentes congeladas durante cada corrida.
- Para cada tarea: causa, dependencias, prueba que falla antes, corrección, prueba que pasa después y evidencia de versión cargada.
- No usar cantidad de manejadores registrados como avance de hechizos. Informar por separado cobertura de ciclo, efectos verificados, hechizos completos y pruebas de cliente.
- No repetir auditorías ya acreditadas salvo cambio de dependencia, fallo nuevo o caso pendiente. No crear un camino alternativo del harness que evite validaciones de producción.
- No anunciar una raza terminada por pasar Listo o dos turnos. No anunciar una corrección cargada antes de comprobar boot y salud.

No hay una estimación de plazo total defendible todavía: falta una matriz de lanzamientos/eventos suficientemente completa para cuantificar los pendientes. La fase2 debe producir esa lista; luego se estiman bloques de trabajo usando causas y dependencias reales.
