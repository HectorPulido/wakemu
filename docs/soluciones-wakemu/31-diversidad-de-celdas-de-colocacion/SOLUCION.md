# Solución propuesta — 31

Variar formaciones legales por encuentro sin incoherencia entre jugadores o reconnect.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Distinguir determinismo de defecto

generate ordena semillas/vecinos/distancias y ofrece seis por equipo. Con igual entrada produce igual formación: eso no implica misma forma en todos los mapas. Registrar candidatos/terreno y capturas para precisar diversidad esperada y respetar diseños oficiales si existen.

## 2. Definir política de formación

Preferir layouts catalogados por zona/encuentro o muestrear candidatos legales con RNG fijo por fight. Acordar tamaño/estrategia y si se preserva posición inicial. No colocar celdas al azar sin reachability ni fabricar suelo en huecos.

## 3. Elegir una vez bajo versión

Generar propuestas sobre índice de terreno cacheado 0; validar equipos disjuntos, altura y acceso. Persistir seed/layout completo con fight_id antes de bootstrap; retry/reconnect usa la selección existente, no otra tirada.

## 4. Asignar cupos y casos pequeños

Adaptar cupos a actores 14 y mapa pequeño con regla explícita. Fallar de forma revisable si no hay formación legal, liberando reservas; no devolver celdas del enemigo para completar seis. Carrera join/ready revalida capacity sin regenerar todo el layout.

## 5. Medir diversidad y legalidad

Variar seeds de varios encuentros y comparar layouts; semilla idéntica debe reproducir. Dos jugadores y espectador ven el mismo conjunto. Verificar también rendimiento: diversidad no autoriza reescanear todo el mapa por actor.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Layout elegido una vez por encuentro, legal para todos y persistente a través de sesiones.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
