# Cotejo de código y evidencia

La evidencia incluye los hashes del código ensayado, los diez casos y cada estado intermedio en [probe-reversibilidad.json](../17-aptitudes-y-calculo-de-estadisticas/probe-reversibilidad.json). `storage/build_journal.py`, método `save`, calcula `maximum` y aplica `maximum if hp > 0 and hp == max_hp else min(hp, maximum)`; contrastar la ruta equivalente de `storage/store.py` antes de implementar para que ambas compartan la misma política.

Un cambio concurrente de estas funciones exige repetir el probe y registrar nuevos hashes; estos resultados no certifican una versión desplegada.
