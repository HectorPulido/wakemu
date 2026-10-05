# E18 — Motor de IA táctica de enemigos

El servicio actual solo acerca al enemigo por BFS; el servidor añade un ataque específico de Wonejo y termina turno. Propuesta: reutilizar la arquitectura táctica de `/Users/hectorpulido/dofus/ai-service`, excluyendo Laya, con adaptadores nativos de Wakfu para hechizos, terreno 3D, orientación y ejecución.

[Estado y sistemas reutilizables](COTEJO.md) · [Diseño e implementación por etapas](SOLUCION.md) · [Casos de aceptación](PRUEBAS.md) · [Evidencia ejecutada](probe-ia-actual-y-fuentes.json).

Preferencias del usuario: decisiones por tipos de hechizo y capacidades, actuación individual/equipo, buscar espalda y aprovechar elevaciones. Auditoría y especificación, sin implementar ni desplegar. Dependencias: motor común de hechizos de la otra sesión, 0 (rendimiento), 14/15/29 (combates compartidos/instancias), E01 (configuración y recuperación).

## Plan ampliado

[Diferencias y portabilidad por subsistema](DIFERENCIAS-Y-PORTABILIDAD.md) · [Contratos, algoritmo y evaluación táctica](CONTRATOS-Y-ALGORITMO.md) · [Etapas, archivos y aceptación](PLAN-DE-IMPLEMENTACION.md).

## Prioridad y decisiones

**Prioridad 6 en el índice general**, condicionada a autoridad NPC/preview del motor común y medición de rendimiento. No requiere decisiones adicionales del usuario para avanzar. [Pendientes técnicos y alcance acordado](FALTANTES.md).
