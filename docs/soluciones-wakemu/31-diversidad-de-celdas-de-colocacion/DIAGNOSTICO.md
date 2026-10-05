# Diagnóstico — 31

## Contexto registrado

**Confirmado por código:** `combat/combat_placement_cells.py::generate` genera una formación determinista desde posiciones de actores y terreno dirigido. Ordena semillas, vecinos y candidatos por distancia y coordenada; el cupo predeterminado es seis celdas por equipo. No utiliza RNG ni diseños alternativos. Con iguales posiciones y geometría devuelve la misma formación. No significa que todos los mapas tengan exactamente las mismas celdas: depende del terreno y las semillas.

**Posible solución del servidor:** definir variantes de formación por zona/encuentro o muestreo controlado entre candidatos legales, persistiendo el resultado elegido para que ambos equipos y la reconexión reciban lo mismo. Conservar celdas iniciales ocupadas, equipos disjuntos, altura válida y alcanzabilidad; no fabricar suelo ni aumentar el coste de escanear el mapa descrito en el ítem 0.

**Validación:** varios encuentros con posiciones iguales y diferentes; diversidad según política, semilla reproducible, mapas pequeños/desniveles, cupos y reconexión sin regenerar otra formación. Las pruebas existentes comprueban legalidad de formación, no diversidad gráfica.

## Lectura actual

El generador debe cotejarse con conectividad y terreno antes de variar celdas. Aleatoriedad sin invariantes puede producir equipos inaccesibles o solapados.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Diversidad deseada y layouts oficiales por zona si existen.
- Tamaño de equipo/cupos y fallback en mapas pequeños.
- Algoritmo/seed policy y métrica de variedad aceptada.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
