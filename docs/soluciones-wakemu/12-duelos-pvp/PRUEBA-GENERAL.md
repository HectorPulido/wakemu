# Prueba conjunta: duelos y espectadores

**Estado: habilitada.** r9 está desplegada y saludable; pruebas automáticas y TLS aprobados. Falta confirmar la interfaz mediante este caso completo.

Usa dos clientes con Adael y Krill, de niveles cercanos, para poder atacar desde ambos lados sin terminar el duelo con el primer golpe. Aquí A es quien inicia el combate y B es el segundo cliente. No necesitas reiniciar servicios ni crear personajes.

1. Entra con ambos en el mismo mapa, cerca y fuera de combate. Anota XP, kamas, objetos y posiciones. Deja al menos una casilla libre en la bolsa de A.
2. A desafía a B desde su menú contextual. B rechaza. Esperado: B ve el diálogo Aceptar/Rechazar y al rechazar desaparece; no empieza combate y ambos pueden caminar. A recibe un aviso local: el cliente nativo no abre un modal Cancelar en el iniciador.
3. Espera60 segundos, desafía de nuevo y acepta. Pulsa Listo primero con A y después con B. Esperado: dos equipos contrarios, transición a combate sin errores y cada cliente controla a su personaje.
4. Acércalos a casillas adyacentes y usa el puño contra el otro personaje en el turno correspondiente; repite desde el otro cliente en su turno. Esperado: ambos ataques se ejecutan y reducen vida del adversario, sin mensajes de dirección ausente.
5. En el siguiente turno no hagas acciones y deja vencer el contador. Esperado: el turno avanza al otro personaje en ambas pantallas; el contador se reinicia y ese personaje puede actuar.
6. Usa el botón de abandonar de A y confirma si aparece una confirmación. Esperado: termina el duelo en ambos clientes, A pierde, no se queda contador en0 ni aparece error de participante. Cierra primero el resumen de A y deja abierto el de B durante diez segundos: A debe poder caminar y abrir inventario, sin volver al duelo. Después cierra el resumen de B. Esperado en ambos: vida completa, posiciones originales y cero XP/kamas/objetos ganados.
7. Espera60 segundos y abre otro duelo. Antes de pulsar Listo, B abandona. Esperado: se cancela la colocación y ambos recuperan exploración, sin premios ni combate residual.
8. Espera60 segundos y abre otro duelo, acepta y pulsa Listo en ambos. Cierra por completo el cliente de B durante el combate. Esperado: A vuelve a exploración tras el abandono. Reabre B y entra; cierra el resumen pendiente si aparece. Vida completa, cero premios y movimiento normal en ambos.
9. Con A escribe en chat general:

   ```text
   !mob 4196 1 1
   ```

   Esperado: aparece un Mimic dulce nivel1. A lo ataca y NO pulsa Listo todavía. No debe aparecer «Fight/actor already registered». B debe ver el marcador de espadas junto al combate.
10. B hace clic derecho sobre las espadas y elige observar. Esperado: ve la colocación; no aparece como combatiente ni puede mover actores o lanzar sus hechizos.
11. A pulsa Listo y pasa un turno sin matar al Mimic. Esperado en B: ve el inicio y avance del combate. B sale del modo espectador, camina y vuelve a observar. Esperado: recupera el mapa al salir y el estado actual al volver, sin regresar a la colocación inicial.
12. A derrota al Mimic. Esperado: desaparecen las espadas y termina la observación. A recibe recompensas; B no recibe XP, kamas ni botín. Ambos pueden caminar y abrir inventario.
13. Anota las cantidades finales. En ambos clientes cambia al selector y vuelve a entrar; luego cierra/reabre ambos clientes. Esperado: cantidades y nivel conservados, sin invitaciones ni combates residuales, movimiento e inventario normales.

Si falla un paso, registrar número, personaje y hora aproximada; captura de ambas pantallas si es posible. No cerrar issues12/16 solo por tests de paquetes: esta prueba debe confirmar la interfaz completa.
