**No repetir: r13 visual rechazada por el usuario. El caso queda suspendido hasta reproducción y comprobación visual por agentes.**

# Prueba completa de espadas, espectadores y entrada compartida

Habilitada en r13 (`4b1bf709`), posterior a rendición/reconexión/premios aceptados por el usuario. Dos clientes A=Wayo y B=Krozz, vivos y fuera de combate, mismo mapa. No repetir lo ya aprobado.

1. A escribe `!mob 4196 1 1` y ataca sin Listo. B debe ver espadas donde empezó la pelea. Si no aparecen, detener esta prueba y registrar fallo.
2. B hace clic derecho en espadas y observa. A pulsa Listo. B ve acciones/turnos y no controla actores.
3. B sale, camina y vuelve a observar. Recupera el estado actual del combate.
4. A derrota al Mimic. Espadas desaparecen, ambos vuelven a explorar; solo A recibe premios.
5. A genera otro Mimic con `!mob 4196 1 1` y ataca sin Listo. B se une desde las espadas al equipo de A. Ambos aparecen en el mismo equipo, cada cliente controla su personaje.
6. Ambos pulsan Listo y derrotan al Mimic. Cada uno recibe resultados y puede caminar, abrir inventario e iniciar otra pelea.
7. Cambia al selector y vuelve con ambos. Premios conservados, ninguna pelea residual.

Rendición de un miembro mientras otros continúan sigue en desarrollo; no se cubre con este caso.
