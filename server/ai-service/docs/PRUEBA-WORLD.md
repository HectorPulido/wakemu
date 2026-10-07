# Prueba general de integración world/IA

Estado actualizado y evidencia: [README de E18](../../../docs/soluciones-wakemu/E18-ia-tactica-enemigos/README.md).

World `3af10843cbc6`, AI `26576b10f2bb`. Sin reinicio nuevo de world;
contador propio **1/3**. Catálogo completo sellado: 13.269 entradas.
Suite final: **459 pruebas OK**, 115,552 s de tests/116,222 s de validación,
169 imports del motor actual congelado y ninguno externo. 60 focalizadas OK.
Evidencia: `.runtime/local/e18-ai-package-layout-final-full-suite.log`.
Benchmark final: ataques 2/2, 4/4 y 6/8; 14/14 movimientos, sin fallback ni
fallos de invariantes, tiempos 6,788–9,686 s. Fracción productiva 0,25.
Aceptación manual y carga de cuatro encuentros siguen pendientes.
Presupuesto predeterminado de turno 10 s. Caché persistente del catálogo y
preparación completa de objetivos/rutas separada del trabajo de exploración.
El formato fragmentado permanece desactivado por rendimiento.

La aceptación manual del primer turno y de una pelea completa sigue pendiente.
El banco nativo usa encuentros privados y no acredita las animaciones del cliente.
No modificar ni reiniciar world para ejecutar esta prueba.

## Automática

Desde la raíz, validación congelada contra la imagen nativa actual:

```sh
.runtime/e18-venv/bin/python .runtime/local/e18-ai-package-layout-current-world-run.py
```

Incluye todos los tests del SDK y tres módulos de integración nativa; verifica
que los imports nativos provengan de `.runtime/e18-ai-layout-live-3af10843cbc6`.
Es un artefacto local de validación, no un cambio de fuentes de world.

Para los módulos de combate adicionales, con los requisitos de
`server/requirements.txt` instalados:

```sh
PYTHONPATH=server .runtime/e18-venv/bin/python -m unittest tests.test_combat_tactical_ai tests.test_combat_ai_capabilities tests.test_combat_npc_attack tests.test_combat_spell_transaction tests.test_combat_movement_runtime tests.test_combat_ai tests.test_combat_ai_client tests.test_ai_service
PYTHONPATH=server:server/ai-service .runtime/e18-venv/bin/python -m unittest discover -s server/ai-service/tests -p 'test_*.py'
```

La compilación inicial de catálogos nativos es costosa; las pruebas del mismo
proceso comparten el catálogo inmutable y sus caches. World lo precalienta antes
de abrir listeners. No medir esa compilación como tiempo de búsqueda de la IA.
Además de fixtures enfocadas, hay un ensayo HTTP sobre7075 celdas completas
y24556 aristas. No sustituye la aceptación conectada al juego.

## Una partida completa con el puente activo

1. Abrir el cliente habitual y entrar con un personaje de pruebas en Amakna,
   mapa 1134, instancia 0. En chat escribir `!pos`: debe confirmar mapa/instancia.
2. Escribir `!mob 5525 1 2`. Debe aparecer un grupo de dos Wonejos nivel 1.
   El comando elige celdas libres cercanas; no hacen falta coordenadas manuales.
3. Atacar ese grupo. Durante colocación dejar al personaje a varias celdas de
   los enemigos y marcar Listo. Deben empezar turnos sin congelar la colocación.
4. Dejar pasar turnos del personaje. Los Wonejos deben recorrer solo celdas
   libres y aristas legales, con PM descontados. Al alcanzar un blanco válido
   deben lanzar su habilidad 7962; sin tiro/rango legal no deben dañarlo.
5. Observar un turno estando adyacente. Cada Wonejo puede atacar al personaje
   **una vez por turno** por su límite nativo por blanco, aunque tiene un máximo
   de dos lanzamientos globales por turno. No debe golpear repetidamente gratis.
   Daño y armadura proceden del motor común, no de un valor calculado por la IA.
6. Atacar y derrotar un Wonejo. El superviviente debe actuar sobre el roster
   actualizado, sin repetir acciones sobre el muerto ni entrar en una celda viva
   ocupada. Si tenía ese foco, debe descartarlo.
7. Terminar el combate. Deben aparecer resultados y poder volver al mundo.
   Iniciar otro combate: la memoria/identidad del encuentro anterior no debe
   arrastrar foco ni acciones antiguas.

Para acreditar el caso del jalató, tras volver a entrar y terminar el combate
anterior, escribir `!mob 1 8 2` (jalatós de nivel 8). Empezar un combate nuevo
y quedar a varias celdas. Deben acercarse sin entrar en celdas ocupadas y gastar
PM. Su habilidad 5767 todavía carece de árbol ejecutable: no se espera daño,
y el log debe indicar `Unsupported native NPC effect roots`, sin TypeError.
Esto comprueba movimiento general pese a ataques aún pendientes.

En otra terminal, observar la evidencia:

```sh
tail -n 2000 .runtime/local/logs/game-server.jsonl | rg 'combat_monster_tactical_action|combat_finished|combat_test_turn_ack_rejected|combat_monster_tactical_policy_rejected'
```

Esperado: eventos `combat_monster_tactical_action` con `action`, intención,
componentes de score, previews y motivos de descarte; después `end_turn` y flujo
normal del siguiente turno. No debe haber rechazos repetidos de ACK ni traceback.
`13510` es la barrera de fin de turno. Cada acción se publica en un bloque FIFO
nativo antes de redecidir; no existe un ACK acreditado por cada ataque.

El catálogo NPC de efectos exportado actualmente acredita Wonejo. Otros ataques
requieren sus efectos/condiciones soportados; que aparezca una habilidad en csd
no acredita que el runtime ya pueda ejecutar su árbol. Una rama obligatoria
faltante debe constar como descarte y no producir daño/costes/paquetes parciales.
Curación, armadura, AoE y otras capacidades se seleccionarán por deltas cuando
sus previews nativos sean ejecutables; no se promete su disponibilidad actual.

## Puente final y límites acreditados

El cambio final de código fuera de AI reemplaza únicamente
`pass_test_monster_turn` en `server/local_game_server.py`. Compose añade el
volumen read-only `server/ai-service:/app/ai-service` y selecciona la imagen
validada. La imagen conserva todos los demás bytes del world vivo; no se
reconstruyó el checkout de otros agentes. El hook entrega globals y scopes
completos; toda selección de dependencias y publicación permanece en AI.

Presupuesto normal de decisión/commit:5s cooperativos; máximo12 acciones.
El fallback nativo de cierre puede terminar después del presupuesto. En el
ensayo compartido completo más reciente, ataque a4,738s y publicación a5,029s,
ACK pendiente sin cliente simulado. Suite276 aprobada; incluye rodeo+BACK
con daño nativo real y contrato de curación fuera de raíz tras escaleraXYZ.
La primera preparación del SDK en una sesión fría puede agotar el presupuesto;
ninguna respuesta tardía debe ejecutarse. Las precargas no acreditan un límite
duro de latencia. Foco e historial confirmados y corredores nativos de tiro están implementados
en SDK; la aceptación de corredores y los roles avanzados/corpus ampliado
siguen pendientes; esta prueba acredita integración básica, no el sistema E18
completo. En world compartido futuro la publicación usa Registry y outboxes
para todos los participantes; el world vivo actual usa entrega local.
