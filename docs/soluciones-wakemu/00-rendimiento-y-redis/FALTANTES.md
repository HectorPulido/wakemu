# Información pendiente — 0

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Latencia objetivo de p 95/p 99 y carga esperada (jugadores, combates, grupos). | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 2 | Medición completa que reproduzca los 20 s reportados; las muestras parciales no la sustituyen. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Qué dominios deben diferirse exactamente 20 minutos y qué barreras inmediatas deben mantenerse. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 4 | Configuración Redis cargada, garantía AOF/replicación y política ante pérdida del host. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |


1. Latencia esperada: La minima posible, no hay una latencia objetivo
2. Los 20 segundos eran un ejemplo (por ejemplo en combate o al luchar)
3. Hay que revisar que dominios tenemos, pero en si hay que tocar la base de datos lo menos posible, podemos usar como ejemplo la arquitectura de este server de dofus: /Users/hectorpulido/dofus/ai-service
4. Podemos persistir en disco redis cada cierto tiempo usando un hilo alterno para no relentizar nada, tambien agregar sistemas de graceful shutdown

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
