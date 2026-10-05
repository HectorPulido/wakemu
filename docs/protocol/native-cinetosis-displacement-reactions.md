# Cinetosis y finalización de desplazamientos

El cliente instalado describe Cinetosis5041 así: aplica4801 y los enemigos sufren daño cuando el sacrógrito los desplaza después; en Berserker produce daño adicional al lanzamiento. El árbol original coincide:415995/417109 son daño condicionado a HasState(9315,caster). 9315 se llama Berserker. La innata4464 lo aplica mediante416965→416966 al inicio1003 cuando HP%<50 (y416581→416582 en otros eventos). Las pruebas dañan el fixture antes de inicializar; no insertan el estado.

4801 contiene dos suscripciones:196925(variante0)→416111 y416112(variante1)→416113. Ambas escuchan2128 en aZJ(canal3), con criterio GetTriggeringEffectCaster()==GetEffectCaster(), casterCode1, targetCode2, sin inversión ni globalidad. fyW.guW=false permite ambas raíces. Cada hijo produce daño de aire equivalente al nivel del estado antes de mitigación. Se conservan ambos listeners y UID; no se deduplican por nombre.

## Productor emulado: inferencia explícita

No encontramos productor2128 en los bytecodes distribuidos; las rutinas originales de desplazamiento usan sus propios eventos185/188/etc. La emisión adicional2128 es una **inferencia de servidor** basada en el texto y las suscripciones originales, no una llamada cliente acreditada. OrdinaryDisplacementEvents.displacement_completed la entrega una vez por actor cuya posición realmente cambió, después de la mutación y las fases originales. Conserva caster, definición, UID y contexto de la fuente; pasa por replay, selección, criterios y handlers comunes. No identifica hechizos, clases ni estados particulares. Incluye push/pull/teleport/swap soportados; no emite para intento bloqueado o posición idéntica. Flag5 conserva la supresión nativa de reacciones de nivel1, que ya aplica el replay.

La cadencia por finalización (en lugar de por casilla) también es inferida: el texto instalado no dice «por casilla». No se presenta como bytecode servidor original.

## Validación

`PYTHONPATH=server:server/tests python3 -m unittest test_combat_displacement_reactions test_combat_cinetosis_chain -q`

La cadena real común usa mapa1134, geometría/LOS originales, NPC3646 nivel12 HP84 y sus resistencias originales. Sacro20/200 instala sus innatas y lanza5041 seguido5030:

- Normal:5041 deja HP84; tras tirón HP80/56, dos impactos mitigados correspondientes a nivel3/21.
- Berserker legítimo:5041 ya daña HP84→78/35; el tirón continúa dañando.
- Sin4801:5030 desplaza, HP84 no cambia.
- Fulgor25/200 teleporta al lanzador y aumenta armadura8/24 tras admitir flag5.

Cada transacción conserva intacto el origen (checkpoint) y el informe registra variantes, posiciones, recursos, estados/UID y paquetes. Las pruebas ligeras comprueban posición idéntica, swap, identidad de fuente y criterio con otro caster. Estas son verificaciones offline del motor, no de GUI. El caso NPC5525 HP12 letal expuso una elegibilidad de cadáver separada, asignada a otra corrección; no se oculta con HP inventado.

## Ampliación: orientación303 tras intercambio

Asalto5040 contiene intercambio422 y orientación303, tanto normal como crítico. La definición416125/416126 tiene parámetros[9,0]. `eWF.C` original lee exclusivamente índice0:modo9 gira el objetivo hacia el caster, calculando dirección con aBA/aBz; el segundo parámetro no se usa. El guard del handler exigía exactamente un parámetro y rechazaba esta definición válida. Se corrige para admitir parámetros extra, sin interpretar sus valores. `ProbeNativeOrientation303` ejecuta C/c originales y verifica modos0,1–4,6–11 y propiedad51 que impide girar. Siete pruebas del handler pasan; la cadena completa de Asalto debe registrarse aparte cuando se ejecute.
