# Prueba general de grupos

Ejecutar únicamente después de confirmar el despliegue. Usa dos clientes con personajes distintos, por ejemplo Audiluna y Prueba Oficios. No necesita objetos ni comandos de administrador.

1. Coloca ambos personajes cerca. Desde Audiluna, abre el menú del otro personaje y elige invitar al grupo. Rechaza desde el segundo cliente. Esperado: aparece la invitación y no se crea grupo al rechazar.
2. Repite la invitación y acepta. Esperado: ambos clientes muestran los mismos dos miembros y Audiluna como líder.
3. Escribe en General `/p prueba grupo` desde cada cliente. Esperado: ambos reciben el mensaje en el canal de grupo. Después, aleja al segundo personaje cambiando de mapa por un transporte que ya funciona. Esperado: los dos conservan el grupo, sin añadir miembros ni perderlos.
4. Cambia de personaje en el segundo cliente y vuelve al invitado. Esperado: recupera el mismo grupo. Audiluna no necesita volver a invitarlo.
5. Desde el menú del miembro en el panel del grupo, transfiere el liderazgo al segundo personaje. Esperado: ambos muestran al mismo nuevo líder; ese personaje puede expulsar a Audiluna.
6. Expulsa a Audiluna desde el segundo cliente. Esperado: ambos quedan sin grupo al quedar menos de dos miembros. No basta con que desaparezca en una sola pantalla.
7. El segundo personaje invita otra vez a Audiluna; acepta. Esperado: ambos recuperan un grupo con el segundo personaje como líder.
8. El líder sale voluntariamente del grupo. Esperado: ambos quedan sin grupo. Con tres o más miembros, salir el líder promueve al más antiguo; esa rama se verifica automáticamente.
9. Después de quedar ambos sin grupo, intenta `/p fuera del grupo`. Esperado: no llega ningún mensaje de grupo ni se crea una party. Cambia de personaje y vuelve en ambos clientes. Esperado: permanecen sin grupo, sin roster residual ni invitaciones pendientes visibles.

Si ya hay un tercer cliente abierto, comprueba que no recibe roster ni invitaciones destinadas a los otros dos. Privacidad, cupo seis, rechazo de requests falsos y generaciones sustituidas también se cubren automáticamente.
