# Familia28: eXc muerte directa

Contrato original contrastado mediante javap eXc/ffw/ffe y ProbeNativeKill28.

- Constructor bbx añade evento192; bcd=true.
- C parámetro0==1 activa DONT_TRIGGER_KO, ausencia de parámetros false.
- c con targetnull mu(true); sin característicaHP fRS yreturn.
- HP PA.aZg fija al mínimo autoritativo, no calcula daño ni absorbe armadura.
- Opcional ffe.seI es DONT_TRIGGER_KO, no propiedad genérica de muerto.
- Si KO_TIME_BEFORE_DEATH existe, PA.or(0) se aplica después.
- Amount Qe permanece separado de la modificación de HP.

Probe original PASS: HP con mínimo5 pasa80→5, relojKO3→0, propiedad opcional exacta y suppressnull. Esto no prueba transición FSM/KO ni deliveryPR; ambos deben integrarse antes de declarar soporte. El servidor ordinario actualmente registra muerte por daño: no reutilizarlo como si eXc fuese daño o simular eventos de golpe. Falta acreditar la transición común de vida y el evento192/retirada.
