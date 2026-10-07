# Prueba general: dos personajes en un combate compartido

Esta prueba es para la candidata que contiene el adaptador de combate compartido y la corrección de recompensas al subir de nivel. No uses comandos de paquetes, scripts de prueba ni identificadores internos. La única preparación administrativa es el comando de aparición indicado abajo.

## Preparación

1. Abre dos clientes y entra con los personajes existentes **Audiluna** y **Adael**. Déjalos en el mismo mapa, juntos y fuera de combate. Ambos deben estar disponibles para jugar.
2. Forma un grupo con ambos personajes si todavía no lo tienen. Desde el cliente, invita al otro personaje y acepta la invitación en el segundo cliente. Confirma que los dos aparecen en el mismo grupo.
3. Usa el chat del juego para ejecutar:

   ```text
   !mob 4196 1 1
   ```

   Hazlo una sola vez desde Audiluna. Debe aparecer un Mimic dulce de nivel1. Atácalo con Audiluna para abrir la colocación, pero no pulses Listo hasta que entre Adael.

## Entrada y colocación

4. En el panel del grupo, abre el menú contextual del personaje que ya está en combate y elige la acción nativa para unirse a su combate. Si el cliente muestra una confirmación para unirse, acéptala. Esta ruta corresponde al menú de miembro del grupo: el bytecode del cliente consulta al objetivo del menú y contiene el diálogo `party.question.joinPartyMemberInFight`; si la opción no aparece, anota que la prueba quedó bloqueada en el cliente y no intentes sustituirla con un paquete manual.
5. Verifica que Adael entra en **el mismo** encuentro: aparecen los mismos monstruos y ambos personajes pueden colocar su actor en una celda libre. No debe abrirse un segundo combate independiente.
6. Coloca ambos personajes y marca listo con cada cliente. Espera que el servidor inicie el turno. Comprueba que el orden de turnos y el estado de listo concuerdan en ambas pantallas.

## Turnos, resultado y persistencia

7. Juega algunos turnos alternando los clientes según el orden mostrado. Cuando uno actúa, el otro cliente debe reflejar el cambio sin tener que enviar una acción propia. No envíes acciones desde el personaje cuyo turno no está activo.
8. Termina el combate normalmente. Comprueba en ambos clientes el resultado y el retorno al mapa; cada personaje debe recibir su propio resumen y sus cambios de experiencia, kamas e inventario. La cantidad puede variar con la política de recompensas y las tiradas; no uses un valor fijo como criterio.
9. Cierra y vuelve a seleccionar Adael. Comprueba que regresó al mismo mapa y que sus cambios de experiencia, nivel, kamas e inventario siguen guardados. Repite la reconexión con Audiluna si quieres verificar ambos propietarios.

## Resultado esperado

- Solo existe un encuentro compartido y ambos participantes ven el mismo roster y progreso.
- El servidor conserva la secuencia de acciones; el cliente que espera recibe actualizaciones sin tener que generar una solicitud de juego para provocarlas.
- El cierre entrega y persiste las recompensas de cada propietario una sola vez. Reconectar no duplica premios ni deja el personaje bloqueado en combate.
- Ambos personajes vuelven al mundo y pueden moverse o iniciar otra actividad.

Registra cualquier paso que no ocurra, el personaje afectado y el mensaje visible. Si la opción nativa para unirse no aparece o no permite entrar, detén la prueba en ese paso: la inspección confirma el flujo nativo y el handler del servidor, pero esta guía no afirma que la opción visual haya sido validada en esta sesión.
