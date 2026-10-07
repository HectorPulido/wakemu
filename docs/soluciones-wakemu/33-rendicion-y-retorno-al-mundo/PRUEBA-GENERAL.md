# Prueba completa: PvE, rendición, reconexión, entrada y espectadores

**Habilitada en r12 (`bcfd5fe7`).** Desplegada en el único `world`, base habitual; verificadas pruebas automáticas y conexiones TLS de rendición/reconexión.

Usar dos clientes: A=Wayo, B=Krozz; mismo mapa, fuera de combate, ambos vivos. Anotar XP, kamas y objetos. No requiere borrar personajes ni cambiar la base.

1. A escribe en general `!mob 4196 1 1`. Esperado: aparece un Mimic dulce nivel1.
2. A ataca, sin pulsar Listo. Esperado: colocación; B ve espadas en el mundo. B hace clic derecho sobre las espadas y elige observar. Esperado: ve colocación, no aparece como combatiente.
3. A pulsa Listo, camina un paso en distintas direcciones y pasa un turno. Esperado: dirección final coincide con el último paso, sin giro fijo abajo-izquierda; B ve acciones/avance y no controla actores.
4. A se rinde y confirma. Esperado: ambos salen de combate/observación; A puede caminar y abrir inventario, conserva heridas autoritativas y no recibe XP/kamas/botín. El Mimic queda disponible; desaparecen las espadas.
5. A vuelve a atacar al mismo Mimic. Esperado: colocación nueva, sin «Fight/actor already registered». Cierra completamente el cliente de A durante colocación; vuelve a entrar. Esperado: exploración sin pelea residual.
6. A escribe otra vez `!mob 4196 1 1` y ataca al nuevo Mimic. Esperado: nueva colocación sin rechazo de registro. A se rinde antes de Listo. Esperado: vuelve a exploración, inventario/movimiento disponibles.
7. A cambia al selector y vuelve. Esperado: carga normalmente, sin pantalla de carga infinita. Inicia otra pelea con Mimic disponible. B elige observar las espadas; A pulsa Listo.
8. B sale del espectador, camina y vuelve a observar. Esperado: recupera el estado actual del combate. A mata el Mimic. Esperado: A recibe premios y B ninguno; ambos vuelven al mundo y pueden caminar/abrir inventario.
9. A genera otro Mimic con `!mob 4196 1 1`, lo ataca sin Listo. B usa las espadas para unirse al equipo de A. Esperado: ambos aparecen en el mismo equipo, cada cliente controla solo su personaje. Pulsa Listo en ambos y derrota al Mimic. Esperado: ambos reciben sus resultados privados y vuelven a exploración sin bloqueos.
10. Anota cantidades finales, cambia al selector y vuelve con ambos; después cierra/reabre ambos clientes. Esperado: XP/nivel/kamas/objetos conservados, sin ventanas residuales. Ambos pueden iniciar otra pelea y usar transporte.

Registrar paso/personaje/hora si falla. El abandono de un miembro mientras otros continúan requiere cobertura adicional; no se declara implementado por aprobar el caso de propietario único.
