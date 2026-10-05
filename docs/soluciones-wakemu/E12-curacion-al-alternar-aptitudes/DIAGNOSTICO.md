# Diagnóstico comprobado

Con 10 puntos de aptitud, el máximo es 1470. Después de recibir 100 de daño queda en 1370. Quitar esos puntos baja el máximo a 1050 y recorta la salud a 1050. Al devolverlos, el guardado interpreta hp==max_hp como «antes estaba lleno» y asigna 1470: desaparece el daño sin regeneración.

Se reprodujo en SQLite y en el journal Redis simulado. Los casos de daño 1, 100, 419 y 420 se curan; daño 421 deja 1049 al bajar el máximo y no activa esa rama al restaurarlo. El máximo calculado es reversible y repetir la misma hoja no acumula bonus. Por tanto, este resultado demuestra una pérdida de información de salud al alternar, no un cálculo aleatorio del máximo.

El cotejo está en la política de salud de `Store.save_build` y `BuildJournal.save`: el primero recorta al nuevo máximo y un guardado posterior usa la igualdad con ese máximo reducido para inferir salud completa. No se prueban aquí efectos de equipo ni hechizos ni la captura exacta del usuario.
