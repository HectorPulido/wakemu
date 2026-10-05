# Mazmorras: composición de salas y escalado aún no acreditados

## Respuesta a la preocupación del usuario

No se dispone todavía de una tabla verificada que indique los monstruos, cantidades, niveles y colocación de cada sala de la mazmorra Jalató. Tampoco está acreditada una tabla de dificultades con sus multiplicadores de salud, daño, experiencia y botín para la versión instalada. La propuesta anterior de instancias y puertas no resolvía estas dependencias y no debe interpretarse como una solución completa lista para implementar.

La revisión de los módulos/catálogos exportados no encontró un servicio de mazmorras ni un catálogo de composición por sala o de escalado de dificultad. `monsters.json` describe referencias y familias, no dónde aparece cada monstruo en una mazmorra. La familia 68 contiene varias variantes; asignarlas a salas por nivel o poner al jefe junto a cualquier Jalató sería una invención. El sistema de daño de elemento Stasis es distinto de la dificultad Stasis de mazmorra.

## Investigación obligatoria antes de implementar

1. Identificar la versión exacta del contenido instalado y las definiciones nativas de mazmorra, salas y parámetros de dificultad; comprobar qué datos existen en el cliente y cuáles eran exclusivamente del servidor oficial.
2. Para Jalató, cotejar entrada, dungeon_id, mapas/salas/puertas, número de encuentros, referencias y cantidades por sala, nivel de miembros, jefe y condiciones de acceso/salida. Cada campo debe tener procedencia verificable; no completar huecos con una lista arbitraria de la familia.
3. Extraer por dificultad disponible los modificadores separados de salud, daño, resistencias u otras características que correspondan, experiencia, probabilidad de drop y restricciones del botín. Determinar modo competitivo/modulación y tipos de mazmorra que cambian reglas. No usar un multiplicador común para todo.
4. Cotejar orden y redondeo: cuándo se aplica cada modificador respecto de estadísticas base y reglas de XP/drops de los issues 9/10. La configuración debe quedar fijada para la instancia/encuentro para que cambiar una tabla durante una sala no altere recompensas ya comprometidas.
5. Completar una tabla de sala → encuentro y una tabla de dificultad → modificadores con límites, versión y origen. Si un dato no se encuentra en fuentes acreditadas, registrar ese límite expresamente; solo una política configurable del emulador debe etiquetarse como tal.

## Criterios concretos de aceptación

Probar Jalató completa en dificultad mínima, una intermedia y máxima soportada, con composición exacta de cada sala. Comparar estadísticas antes/después, XP y drop de controles con la misma semilla de RNG. Verificar que el selector, la dificultad persistida y la del encuentro coincidan. Ensayar doble entrada, reconexión entre salas, abandono, dos grupos simultáneos y reintento del premio de jefe sin duplicarlo. No certificar salas solo porque una puerta teletransporte.

## Estado real

La investigación nativa ha localizado UI de niveles Stasis y selección, pero eso aún no acredita composición ni fórmulas. Las búsquedas externas no proporcionaron todavía una fuente oficial verificable para esta tabla; no se adoptan cifras de guías de otra versión. No se aplicó ningún cambio de servidor ni se probó una mazmorra completa. Estos faltantes son responsabilidad de investigación del auditor, no decisiones pendientes del usuario.

## Evidencia nueva posterior a esta revisión

Ya se extrajeron 151 definiciones nativas y enlaces de salas por sectores de un mismo mapa. También hay valores concretos de drop normal/competitivo para diez niveles y dos series de XP. Esto reemplaza la incertidumbre anterior sobre existencia de definiciones y cifras de loot, pero no acredita composición por sala ni reglas de derrota. Ver [salas y ciclo](SALAS-Y-CICLO-DE-INSTANCIA.md) y [tablas de dificultad](DIFICULTAD-Y-MULTIPLICADORES.md).

### Cotejo adicional: catálogo de monstruos frente a composición de salas

La ruta nativa `aKU.cno → bam.a(aKU) → bpN.cno → bpU.e(int,String)` acredita que el array contiene referencias de monstruos usadas para buscar mazmorras por nombre de monstruo. El loader también consulta esas referencias en `blk.bG(short)`. Este array no proporciona sala, cantidad, nivel ni posición; no sirve para inventar poblaciones por sala. Además, `aKU.cnl != 0` sigue un registro alternativo en `byX` y evita crear el `bpN` normal: las variantes requieren conservar su relación, no duplicar el mismo catálogo indiscriminadamente. Evidencia y hashes: `probe-semantica-catalogo-monstruos.json`. Sigue pendiente localizar la fuente de composición por sala.
