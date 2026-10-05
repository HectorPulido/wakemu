# Pendientes y decisiones — E18

## Información necesaria del usuario

**Ninguna decisión bloqueante por ahora.** El alcance ya está definido: IA táctica individual y de equipo, reutilización de Dofus sin Laya, espalda/lateral y elevaciones, reglas/configuración en DB y cambios solo del servidor.

Base propuesta para implementación: selector determinista por capacidades y previews; primeras pruebas con repertorios que el motor ya ejecuta. No exigir una lista manual de habilidades, fórmulas, roles ni mapas al usuario: deben extraerse/cotejarse en código y catálogos.

El balance final (agresividad, coordinación y dificultad) se evaluará con perfiles parametrizados y resultados de pruebas; no hace falta fijarlo antes de construir el motor. Si el usuario tiene preferencias adicionales podrán incorporarse, sin bloquear investigación o implementación autorizada.

## Trabajo técnico pendiente

- Generalizar autoridad NPC y preview, coordinando cambios de archivos compartidos con la sesión de hechizos.
- Acreditar orientación final, topología/LOS de mapas seleccionados y callbacks/reacciones de rutas.
- Ejecutar corpus de roles, planes y coordinación con varios encuentros; medir presupuestos y latencia concurrente.
- Verificar sincronización/GUI con personajes de prueba y observers; no pedir al usuario que sustituya estas pruebas por decisiones.

Son tareas técnicas del implementador. E18 sigue sin implementar; estos pendientes no representan solicitud de aprobación ni reactivan el objetivo pausado.
